# orchestrator/dashboard.py
# Main Flask application entrypoint with integrated security hardening.

import logging
import os
import threading
import time

from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

from .celery_app import app as celery_app
from .cli import collect_chain_results, collect_group_results
from .database import init_db, save_phase_result
from .decision_engine import DecisionEngine
from .elasticsearch_client import ElasticsearchClient
from .job_store import playbook_jobs
from .metasploit_api import msf_bp
from .metasploit_socketio import register_metasploit_socketio
from .mcp import mcp_bp
from .prometheus_metrics import metrics_endpoint, update_queue_length
from .tasks import build_phase_workflow
from tools.proxy_config import credentials_configured
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
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "cerberus-x-secret")
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
from .auth0_routes import auth0_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(auth0_bp)  # /auth/sso /callback /logout (Auth0 SDK)

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
    from security.oidc import register_oidc

    register_oidc(oauth)
except Exception:
    pass

es_client = ElasticsearchClient()
socketio = SocketIO(app, cors_allowed_origins="*")
register_metasploit_socketio(socketio)

log_store = []
# playbook_jobs imported from job_store (Redis-mirrored for HA)
DEFAULT_PLAYBOOK = os.environ.get(
    "PLAYBOOK_PATH", "playbooks/complete_dark_arsenal.yaml"
)
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
    "callback",
    "logout",
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
    playbook_jobs.persist(job_id)
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
        decision_engine = DecisionEngine(
            target, job_id=job_id, posture=job.get("posture", "balanced")
        )

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
            save_phase_result(
                target,
                phase_name,
                phase_outputs,
                job_id=job_id,
                org_id=job.get("org_id"),
            )
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
                save_phase_result(
                    target,
                    action_name,
                    action_output,
                    job_id=job_id,
                    org_id=job.get("org_id"),
                )
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
                        target,
                        action_name,
                        action_output,
                        job_id=job_id,
                        org_id=job.get("org_id"),
                    )
                    decision_engine.evaluate_phase(action_name, action_output)
                    decision_engine.mark_actions_fired([action])

            add_log(f"Completed phase {phase_name}")
        from orchestrator.ai.posture import hardening_recommendations, normalize_posture

        posture_n = normalize_posture(job.get("posture"))
        recs = hardening_recommendations(
            job.get("results") or {}, posture=posture_n
        )
        ai = job.setdefault("ai", {})
        ai["hardening"] = recs
        ai["posture"] = posture_n
        job["hardening"] = recs
        job["state"] = "SUCCESS"
        playbook_jobs.persist(job_id)
        try:
            from orchestrator.ai import blackboard

            blackboard.put(
                job_id,
                "hardening",
                {"recommendations": recs, "posture": posture_n},
                org_id=job.get("org_id"),
            )
            blackboard.put(
                job_id,
                "findings.summary",
                {
                    "phases": list((job.get("results") or {}).keys()),
                    "posture": posture_n,
                    "hardening_count": len(recs),
                },
                org_id=job.get("org_id"),
            )
        except Exception:
            pass
        add_log(f"Playbook finished for {target}")
    except Exception as exc:
        job["state"] = "FAILURE"
        job["error"] = str(exc)
        playbook_jobs.persist(job_id)
        add_log(f"Playbook failed for {target}: {exc}", level="ERROR")
        # Audit log for failure
        audit_log("PLAYBOOK_FAILED", {"job_id": job_id, "target": target, "error": str(exc)}, severity="high")


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