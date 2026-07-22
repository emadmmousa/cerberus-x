# orchestrator/dashboard.py
# Main Flask application entrypoint with integrated security hardening.

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
from .mcp import mcp_bp
from .prometheus_metrics import metrics_endpoint, update_queue_length
from .tasks import build_phase_workflow
from tools.proxy_config import ALLOWED_PROTOCOLS, credentials_configured
from tools import proxy_settings
from tools.env_file import clear_oxylabs_keys, upsert_oxylabs_keys
from tools.k8s_proxy_sync import sync_proxy_to_kubernetes
from tools.waf_evasion import evasion_profile

from security.audit import audit_log
from security.rate_limit import limiter
from security.vault_integration import VaultClient
from security.waf import WAFMiddleware
from security.auth import oauth
from scanner import AuthorizationEnforcer

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
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "firebreak-secret")
try:
    app.config.from_object("utils.config.Config")
except Exception:
    pass

from orchestrator.session_config import configure_sessions

configure_sessions(app)

# Register blueprints (existing)
app.register_blueprint(msf_bp)
app.register_blueprint(mcp_bp)

# Aggressive AI / deception / scaling APIs
from .aggressive_api import agg as aggressive_blueprint

app.register_blueprint(aggressive_blueprint, url_prefix="/api")

# Lightweight active scan API
from .scan_api import scan_bp

app.register_blueprint(scan_bp, url_prefix="/api")

# Auth routes
from .auth_routes import auth_bp

app.register_blueprint(auth_bp, url_prefix="/auth")

# Auth0 Regular Web App routes (/auth/sso, /callback, /logout). Registering this
# is what makes SSO login *and* RP-initiated logout resolve; without it those
# paths fall through to the SPA catch-all and silently no-op.
from .auth0_routes import auth0_bp

app.register_blueprint(auth0_bp)

from .api import register_api_blueprints

register_api_blueprints(app)

# Security middleware (scoped WAF; optional limiter)
app.before_request(WAFMiddleware.before_request)
app.after_request(WAFMiddleware.after_request)
app.before_request(AuthorizationEnforcer.before_request)
try:
    limiter.init_app(app)
except Exception:
    pass
try:
    oauth.init_app(app)
except Exception:
    pass

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
    "mcp",
    "auth",
}

# Vault client (no-op when VAULT_TOKEN unset / vault down)
try:
    _vault = VaultClient()
    _vault.start_auto_rotation(interval=900)
except Exception as _vault_exc:  # pragma: no cover
    logger.warning("Vault init skipped: %s", _vault_exc)
    _vault = None


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
    return os.getenv("FIREBREAK_ENV_FILE", "/app/.env")


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


@app.route("/api/proxy/test", methods=["POST"])
def proxy_settings_test():
    """Probe saved Oxylabs credentials (CONNECT to ip.oxylabs.io)."""
    from tools.wrappers._proxy import probe_upstream

    result = probe_upstream()
    status = 200 if result.get("ok") else 502
    return jsonify(result), status


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
    """Return recent results as JSON (ES preferred, SQLite fallback).

    When job_id is provided, scope to that mission only so the UI does not
    hydrate with historical findings for the same target.
    """
    target = request.args.get("target")
    job_id = request.args.get("job_id")
    limit = int(request.args.get("limit", 100))
    if job_id:
        # Job-scoped mission polls must not mix in older target history from ES.
        return jsonify(get_results(target, limit, job_id=job_id))
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
        "level": resolved_evasion.get("level"),
        "random_headers": bool(resolved_evasion.get("random_headers")),
        "obfuscate_payloads": bool(resolved_evasion.get("obfuscate_payloads")),
        "header_injection": bool(resolved_evasion.get("header_injection")),
        "parameter_pollution": bool(resolved_evasion.get("parameter_pollution")),
        "static_extension": bool(resolved_evasion.get("static_extension")),
        "trusted_user_agent": bool(resolved_evasion.get("trusted_user_agent")),
        "origin_discovery": bool(resolved_evasion.get("origin_discovery")),
        "ai_payloads": bool(resolved_evasion.get("ai_payloads")),
        "random_delay_min": resolved_evasion.get("random_delay_min"),
        "random_delay_max": resolved_evasion.get("random_delay_max"),
        "target_waf": resolved_evasion.get("target_waf"),
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
        decision_engine = DecisionEngine(target, job_id=job_id)

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
            save_phase_result(target, phase_name, phase_outputs, job_id=job_id)
            decision_engine.evaluate_phase(phase_name, phase_outputs)

            actions = decision_engine.generate_post_phase_actions(
                phase_name, phase_outputs
            )
            for action in actions:
                action_name = action.get("phase") or f"auto_{action['tool']}_{phase_name}"
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
                job["phases"].append(
                    {"phase": action_name, "task_id": action_result.id}
                )
                action_output = collect_chain_results(action_result, timeout=300)
                job.setdefault("results", {})[action_name] = action_output
                save_phase_result(target, action_name, action_output, job_id=job_id)
                decision_engine.evaluate_phase(action_name, action_output)
                decision_engine.mark_actions_fired([action])

            if decision_engine.state.get("has_session"):
                post_actions = [
                    action
                    for action in decision_engine.generate_post_phase_actions(
                        phase_name, phase_outputs
                    )
                    if action.get("phase") == "post_exploitation"
                ]
                for action in post_actions:
                    action_name = action.get("phase") or f"auto_{action['tool']}_{phase_name}"
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
                    job["phases"].append(
                        {"phase": action_name, "task_id": action_result.id}
                    )
                    action_output = collect_chain_results(action_result, timeout=300)
                    job.setdefault("results", {})[action_name] = action_output
                    save_phase_result(
                        target, action_name, action_output, job_id=job_id
                    )
                    decision_engine.evaluate_phase(action_name, action_output)
                    decision_engine.mark_actions_fired([action])

            add_log(f"Completed phase {phase_name}")
        job["state"] = "SUCCESS"
        add_log(f"Playbook finished for {target}")
    except Exception as exc:
        job["state"] = "FAILURE"
        job["error"] = str(exc)
        add_log(f"Playbook failed for {target}: {exc}", level="ERROR")
        # Audit log for failure
        audit_log("PLAYBOOK_FAILED", {"job_id": job_id, "target": target, "error": str(exc)}, severity="high")


@app.route("/api/run", methods=["POST"])
def api_run():
    """Submit a playbook or AI-mode mission for a target."""
    body = request.get_json(silent=True) or {}
    target = request.args.get("target") or body.get("target")
    if not target:
        return jsonify({"error": "target is required"}), 400

    use_proxy = bool(body.get("use_proxy", False))
    proxy_protocol = body.get("proxy_protocol") or "http"
    if proxy_protocol not in ALLOWED_PROTOCOLS:
        return jsonify({"error": "invalid proxy_protocol"}), 400

    ai_mode = bool(body.get("ai_mode", False))
    nl_goal = str(body.get("nl_goal") or body.get("goal") or "").strip()
    confirm_high_risk = bool(body.get("confirm_high_risk", False))

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
        "ai_mode": ai_mode,
        "nl_goal": nl_goal,
    }

    if ai_mode:
        from .ai.runner import run_ai_mission

        def _ai_job():
            job = playbook_jobs[job_id]
            job["state"] = "STARTED"
            add_log(f"AI mission started for {target} (goal={nl_goal or 'default'})")
            try:
                from orchestrator.ai.prompts import persona_banner

                add_log(persona_banner())
                run_ai_mission(
                    job=job,
                    job_id=job_id,
                    target=target,
                    use_proxy=use_proxy,
                    proxy_protocol=proxy_protocol,
                    evasion=resolved_evasion,
                    nl_goal=nl_goal,
                    confirm_high_risk=confirm_high_risk,
                    add_log=add_log,
                )
                job["state"] = "SUCCESS"
                add_log(f"AI mission finished for {target}")
                audit_log("AI_MISSION_COMPLETE", {"job_id": job_id, "target": target})
            except Exception as exc:
                job["state"] = "FAILURE"
                job["error"] = str(exc)
                add_log(f"AI mission failed for {target}: {exc}", level="ERROR")
                audit_log("AI_MISSION_FAILED", {"job_id": job_id, "target": target, "error": str(exc)}, severity="high")

        threading.Thread(target=_ai_job, daemon=True).start()
        add_log(
            f"Submitted AI job {job_id} for {target} "
            f"(proxy={use_proxy}/{proxy_protocol})"
        )
        return jsonify(
            {
                "task_id": job_id,
                "target": target,
                "state": "PENDING",
                "ai_mode": True,
            }
        )

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
    audit_log("PLAYBOOK_SUBMITTED", {"job_id": job_id, "target": target, "playbook": playbook_path})
    return jsonify({"task_id": job_id, "target": target, "state": "PENDING"})


@app.route("/api/ai/sessions", methods=["GET"])
def api_ai_sessions():
    from .mcp import sessions as mcp_sessions

    return jsonify({"sessions": mcp_sessions.list_sessions(limit=50)})


@app.route("/api/ai/audit/<session_id>", methods=["GET"])
def api_ai_audit(session_id: str):
    from .mcp import sessions as mcp_sessions

    return jsonify(
        {
            "session_id": session_id,
            "audit": mcp_sessions.list_audit(session_id, limit=100),
        }
    )


@app.route("/api/ai/plan", methods=["POST"])
def api_ai_plan():
    """Dry-run planner for UI / debugging."""
    body = request.get_json(silent=True) or {}
    target = (body.get("target") or "").strip()
    if not target:
        return jsonify({"error": "target is required"}), 400
    from .ai import planner

    plan = planner.suggest_next_phase(
        target,
        body.get("results") if isinstance(body.get("results"), dict) else {},
        nl_goal=str(body.get("nl_goal") or ""),
        step=int(body.get("step") or 0),
    )
    return jsonify(plan)

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
    emit("log", {"message": "Connected to Firebreak dashboard", "level": "INFO"})
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