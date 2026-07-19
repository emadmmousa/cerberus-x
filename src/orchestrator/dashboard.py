import logging
import os
import threading
import time
import uuid

from pathlib import Path

import yaml
from celery.result import AsyncResult
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

from .celery_app import app as celery_app
from .cli import collect_chain_results, collect_group_results
from .database import get_results, init_db, save_phase_result
from .decision_engine import DecisionEngine
from .elasticsearch_client import ElasticsearchClient
from .metasploit_api import msf_bp
from .metasploit_socketio import register_metasploit_socketio
from .prometheus_metrics import metrics_endpoint, update_queue_length
from .tasks import build_phase_workflow
from tools.proxy_config import ALLOWED_PROTOCOLS, credentials_configured
from tools import proxy_settings
from tools.env_file import clear_oxylabs_keys, upsert_oxylabs_keys
from tools.k8s_proxy_sync import sync_proxy_to_kubernetes
from tools.waf_evasion import evasion_profile

logger = logging.getLogger(__name__)


def _resolve_evasion(playbook: dict, override=None) -> dict:
    """Build evasion settings from API override or playbook default."""
    raw = override if override is not None else playbook.get("evasion")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        level = raw.strip().lower()
        if level in {"off", "none", "false", "0"}:
            return {}
        return evasion_profile(level)
    return {}

app = Flask(__name__)
app.config["SECRET_KEY"] = "cerberus-x-secret"
app.register_blueprint(msf_bp)

es_client = ElasticsearchClient()
socketio = SocketIO(app, cors_allowed_origins="*")
register_metasploit_socketio(socketio)

log_store = []
playbook_jobs = {}
DEFAULT_PLAYBOOK = os.environ.get("PLAYBOOK_PATH", "playbooks/default.yaml")
_queue_metrics_started = False
STATIC_APP = Path(__file__).resolve().parent / "static" / "app"
_SPA_RESERVED = {
    "api",
    "status",
    "results",
    "metrics",
    "health",
    "ready",
    "socket.io",
}


@app.route("/")
def index():
    spa = STATIC_APP / "index.html"
    if spa.is_file():
        return send_from_directory(STATIC_APP, "index.html")
    from flask import render_template

    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "orchestrator"})


@app.route("/ready")
def ready():
    checks = {"sqlite": True, "elasticsearch": es_client.available}
    try:
        celery_app.control.ping(timeout=1.0)
        checks["celery"] = True
    except Exception:
        checks["celery"] = False
    status = "ready" if checks["sqlite"] else "not_ready"
    code = 200 if status == "ready" else 503
    return jsonify({"status": status, "checks": checks}), code


@app.route("/metrics")
def metrics():
    return metrics_endpoint()


@app.route("/api/proxy/status")
def proxy_status():
    flagged = os.getenv("OXYLABS_PROXY_CONFIGURED", "").lower() in {
        "1",
        "true",
        "yes",
    }
    return jsonify({"configured": credentials_configured() or flagged})


def _env_file_path() -> str:
    return os.getenv("CERBERUS_ENV_FILE", "/app/.env")


def _settings_response(creds: dict | None, *, source: str, **extra):
    body = proxy_settings.public_view(creds, source=source)
    body.update(extra)
    return body


@app.route("/api/proxy/settings", methods=["GET"])
def proxy_settings_get():
    creds = proxy_settings.load_credentials()
    source = (creds or {}).get("source", "none") if creds else "none"
    return jsonify(_settings_response(creds, source=source))


@app.route("/api/proxy/settings", methods=["PUT"])
def proxy_settings_put():
    body = request.get_json(silent=True) or {}
    existing = proxy_settings.load_settings() or proxy_settings.load_credentials()
    try:
        merged = proxy_settings.merge_put_body(body, existing)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        proxy_settings.save_settings(merged)
    except Exception as exc:
        return jsonify({"error": f"redis write failed: {exc}"}), 503

    redis_status = {"ok": True}
    env_status: dict
    try:
        upsert_oxylabs_keys(
            _env_file_path(),
            {
                "OXYLABS_PROXY_USERNAME": merged["username"],
                "OXYLABS_PROXY_PASSWORD": merged["password"],
                "OXYLABS_PROXY_HOST": merged["host"],
                "OXYLABS_PROXY_PORT": str(merged["port"]),
                "OXYLABS_PROXY_PROTOCOL": merged["protocol"],
            },
        )
        env_status = {"ok": True}
    except Exception as exc:
        env_status = {"ok": False, "error": str(exc)}

    k8s_status = sync_proxy_to_kubernetes(merged)
    view = _settings_response(
        {**merged, "source": "redis"},
        source="redis",
        ok=True,
        redis=redis_status,
        env=env_status,
        k8s=k8s_status,
    )
    return jsonify(view)


@app.route("/api/proxy/settings", methods=["DELETE"])
def proxy_settings_delete():
    purge = request.args.get("purge", "").lower() in {"1", "true", "yes"}
    try:
        proxy_settings.clear_settings()
    except Exception as exc:
        return jsonify({"error": f"redis clear failed: {exc}"}), 503

    env_status = {"ok": True}
    k8s_status = {"ok": True}
    if purge:
        try:
            clear_oxylabs_keys(_env_file_path())
        except Exception as exc:
            env_status = {"ok": False, "error": str(exc)}
        from tools.k8s_proxy_sync import clear_proxy_from_kubernetes

        k8s_status = clear_proxy_from_kubernetes()

    return jsonify(
        {
            "ok": True,
            "configured": credentials_configured(),
            "source": "none"
            if not credentials_configured()
            else (proxy_settings.load_credentials() or {}).get("source", "env"),
            "redis": {"ok": True},
            "env": env_status,
            "k8s": k8s_status,
        }
    )


@app.route("/api/playbook")
def playbook_summary():
    """Expose the configured phase pipeline so the UI can pre-render it."""
    playbook_path = request.args.get("playbook", DEFAULT_PLAYBOOK)
    try:
        with open(playbook_path) as handle:
            playbook = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return jsonify({"error": f"playbook not found: {playbook_path}"}), 404

    phases = []
    for phase in playbook.get("phases", []):
        phases.append(
            {
                "name": phase.get("name"),
                "tools": [t.get("tool") for t in phase.get("tools", []) if t.get("tool")],
                "parallel": bool(phase.get("parallel", False)),
                "depends_on": phase.get("depends_on", []),
                "when": phase.get("when"),
            }
        )
    return jsonify(
        {
            "name": playbook.get("name"),
            "evasion": playbook.get("evasion"),
            "phases": phases,
        }
    )


@app.route("/status/<task_id>")
def task_status(task_id):
    if task_id in playbook_jobs:
        return jsonify(playbook_jobs[task_id])
    result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "state": result.state,
        "info": result.info,
    }
    if result.state == "SUCCESS":
        response["result"] = result.result
    return jsonify(response)


@app.route("/results")
def results():
    """Return recent results as JSON (ES preferred, SQLite fallback)."""
    target = request.args.get("target")
    limit = int(request.args.get("limit", 100))
    if es_client.available:
        rows = es_client.search_results(target=target, limit=limit)
        if rows:
            return jsonify(rows)
    return jsonify(get_results(target, limit))


def _run_playbook_job(
    job_id, target, playbook, use_proxy=False, proxy_protocol="http", evasion=None
):
    job = playbook_jobs[job_id]
    job["state"] = "STARTED"
    job["use_proxy"] = use_proxy
    job["proxy_protocol"] = proxy_protocol
    resolved_evasion = evasion if isinstance(evasion, dict) else _resolve_evasion(playbook)
    job["evasion"] = {
        "random_headers": bool(resolved_evasion.get("random_headers")),
        "obfuscate_payloads": bool(resolved_evasion.get("obfuscate_payloads")),
        "random_delay_min": resolved_evasion.get("random_delay_min"),
        "random_delay_max": resolved_evasion.get("random_delay_max"),
    }
    try:
        if use_proxy:
            flagged = os.getenv("OXYLABS_PROXY_CONFIGURED", "").lower() in {
                "1",
                "true",
                "yes",
            }
            if not flagged and not credentials_configured():
                add_log(
                    "use_proxy enabled — ensure workers have OXYLABS_PROXY_USERNAME/PASSWORD",
                    level="INFO",
                )
            else:
                add_log("use_proxy enabled for this run", level="INFO")
        if resolved_evasion:
            add_log(
                "WAF evasion active "
                f"(headers={resolved_evasion.get('random_headers')}, "
                f"delay={resolved_evasion.get('random_delay_min')}-"
                f"{resolved_evasion.get('random_delay_max')})",
                level="INFO",
            )

        init_db()
        decision_engine = DecisionEngine(target)

        for phase in playbook.get("phases", []):
            phase_name = phase.get("name")
            tools = phase.get("tools", [])
            parallel = phase.get("parallel", False)

            # Re-evaluate when/depends after each prior phase updates state.
            should_run, skip_reason = decision_engine.should_run_phase(phase)
            if not should_run:
                add_log(
                    f"Skipping phase {phase_name} ({skip_reason})",
                    level="INFO",
                )
                job["phases"].append(
                    {"phase": phase_name, "error": f"skipped: {skip_reason}"}
                )
                continue

            add_log(
                f"Running phase {phase_name} for {target} "
                f"(parallel={parallel}, proxy={use_proxy})"
            )
            workflow = build_phase_workflow(
                phase_name,
                tools,
                target,
                parallel=parallel,
                use_proxy=use_proxy,
                proxy_protocol=proxy_protocol,
                evasion=resolved_evasion,
            )
            if workflow is None:
                job["phases"].append({"phase": phase_name, "error": "No valid tools"})
                continue
            async_result = workflow.apply_async()
            job["phases"].append({"phase": phase_name, "task_id": async_result.id})
            if parallel:
                phase_outputs = collect_group_results(async_result, timeout=600)
            else:
                phase_outputs = collect_chain_results(async_result, timeout=600)
            job.setdefault("results", {})[phase_name] = phase_outputs
            save_phase_result(target, phase_name, phase_outputs)
            decision_engine.evaluate_phase(phase_name, phase_outputs)

            actions = decision_engine.generate_post_phase_actions(
                phase_name, phase_outputs
            )
            for action in actions:
                action_name = f"auto_{action['tool']}_{phase_name}"
                add_log(f"Auto action {action_name}", level="INFO")
                action_workflow = build_phase_workflow(
                    action_name,
                    [{"tool": action["tool"], "args": action["args"]}],
                    target,
                    parallel=False,
                    use_proxy=use_proxy,
                    proxy_protocol=proxy_protocol,
                    evasion=resolved_evasion,
                )
                if action_workflow is None:
                    continue
                action_result = action_workflow.apply_async()
                action_output = collect_chain_results(action_result, timeout=300)
                job.setdefault("results", {})[action_name] = action_output
                save_phase_result(target, action_name, action_output)
                job["phases"].append(
                    {"phase": action_name, "task_id": action_result.id}
                )

            add_log(f"Completed phase {phase_name}")
        job["state"] = "SUCCESS"
        add_log(f"Playbook finished for {target}")
    except Exception as exc:
        job["state"] = "FAILURE"
        job["error"] = str(exc)
        add_log(f"Playbook failed for {target}: {exc}", level="ERROR")


@app.route("/api/run", methods=["POST"])
def api_run():
    """Submit a playbook for a target; phases run in order."""
    body = request.get_json(silent=True) or {}
    target = request.args.get("target") or body.get("target")
    if not target:
        return jsonify({"error": "target is required"}), 400

    use_proxy = bool(body.get("use_proxy", False))
    proxy_protocol = body.get("proxy_protocol") or "http"
    if proxy_protocol not in ALLOWED_PROTOCOLS:
        return jsonify({"error": "invalid proxy_protocol"}), 400

    playbook_path = request.args.get("playbook", DEFAULT_PLAYBOOK)
    try:
        with open(playbook_path) as handle:
            playbook = yaml.safe_load(handle)
    except FileNotFoundError:
        return jsonify({"error": f"playbook not found: {playbook_path}"}), 404

    evasion_override = body.get("evasion")
    if evasion_override is not None and not isinstance(
        evasion_override, (str, dict)
    ):
        return jsonify({"error": "invalid evasion"}), 400
    resolved_evasion = _resolve_evasion(playbook, evasion_override)

    job_id = str(uuid.uuid4())
    playbook_jobs[job_id] = {
        "task_id": job_id,
        "target": target,
        "state": "PENDING",
        "phases": [],
        "use_proxy": use_proxy,
        "proxy_protocol": proxy_protocol,
    }
    threading.Thread(
        target=_run_playbook_job,
        args=(
            job_id,
            target,
            playbook,
            use_proxy,
            proxy_protocol,
            resolved_evasion,
        ),
        daemon=True,
    ).start()
    add_log(
        f"Submitted playbook job {job_id} for {target} "
        f"(proxy={use_proxy}/{proxy_protocol})"
    )
    return jsonify({"task_id": job_id, "target": target, "state": "PENDING"})


@app.route("/<path:path>")
def spa_fallback(path: str):
    root = path.split("/", 1)[0]
    if root in _SPA_RESERVED:
        return jsonify({"error": "not found"}), 404
    candidate = STATIC_APP / path
    if candidate.is_file():
        return send_from_directory(STATIC_APP, path)
    spa = STATIC_APP / "index.html"
    if spa.is_file():
        return send_from_directory(STATIC_APP, "index.html")
    return jsonify({"error": "not found"}), 404


@socketio.on("connect")
def handle_connect():
    emit("log", {"message": "Connected to Cerberus-X dashboard", "level": "INFO"})
    for entry in log_store[-50:]:
        emit("log", entry)


def add_log(message, level="INFO"):
    entry = {"message": message, "level": level, "timestamp": time.time()}
    log_store.append(entry)
    if len(log_store) > 1000:
        log_store.pop(0)
    socketio.emit("log", entry)


def update_queue_metrics():
    while True:
        try:
            inspect = celery_app.control.inspect()
            active = inspect.active() if inspect else None
            total = sum(len(tasks) for tasks in (active or {}).values())
            update_queue_length(total)
        except Exception as exc:
            logger.debug("Queue metric update failed: %s", exc)
        time.sleep(10)


def start_background_tasks():
    global _queue_metrics_started
    if _queue_metrics_started:
        return
    _queue_metrics_started = True
    threading.Thread(target=update_queue_metrics, daemon=True).start()


if __name__ == "__main__":
    init_db()
    start_background_tasks()
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
else:
    # Import-time start for gunicorn/compose module entrypoints.
    start_background_tasks()
