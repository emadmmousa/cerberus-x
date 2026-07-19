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
from .elasticsearch_client import ElasticsearchClient
from .metasploit_api import msf_bp
from .metasploit_socketio import register_metasploit_socketio
from .prometheus_metrics import metrics_endpoint, update_queue_length
from .tasks import build_phase_workflow
from tools.proxy_config import ALLOWED_PROTOCOLS, credentials_configured

logger = logging.getLogger(__name__)

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


def _run_playbook_job(job_id, target, playbook, use_proxy=False, proxy_protocol="http"):
    job = playbook_jobs[job_id]
    job["state"] = "STARTED"
    job["use_proxy"] = use_proxy
    job["proxy_protocol"] = proxy_protocol
    try:
        if use_proxy and not credentials_configured():
            add_log(
                "use_proxy requested but worker Oxylabs credentials may be missing",
                level="WARNING",
            )

        for phase in playbook.get("phases", []):
            phase_name = phase.get("name")
            tools = phase.get("tools", [])
            parallel = phase.get("parallel", False)
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
        args=(job_id, target, playbook, use_proxy, proxy_protocol),
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
