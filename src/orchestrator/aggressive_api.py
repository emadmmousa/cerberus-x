"""Aggressive AI / dynamic playbook / deception / scaling API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests
from flask import Blueprint, jsonify, request

from orchestrator.ai_decision import AIDecisionEngine
from orchestrator.dynamic_playbook import DynamicPlaybookCompiler
from security.audit import audit_log
from services.deception import DeceptionEngine
from utils.global_state import get_session_state
from workers.scaling import DynamicScaler

logger = logging.getLogger(__name__)

agg = Blueprint("agg", __name__)
_ai_engine = AIDecisionEngine()
_deception = DeceptionEngine()
_scaler = DynamicScaler()

_PLAYBOOK_ROOT = Path(__file__).resolve().parents[2] / "playbooks"


@agg.route("/aggressive/decide", methods=["POST"])
def aggressive_decision():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    results = data.get("results")
    if not session_id or results is None:
        return jsonify({"error": "Missing session_id or results"}), 400
    plan = _ai_engine.decide(session_id, results)
    audit_log("AGGRESSIVE_DECIDE", {"session_id": session_id, "count": len(plan)})
    return jsonify({"plan": plan})


@agg.route("/aggressive/execute", methods=["POST"])
def execute_aggressive():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    results = data.get("results")
    if not session_id or results is None:
        return jsonify({"error": "Missing session_id or results"}), 400
    count = _ai_engine.execute_next(session_id, results)
    audit_log("AGGRESSIVE_EXECUTE", {"session_id": session_id, "count": count})
    return jsonify({"status": "executed", "scheduled": count})


@agg.route("/playbook/dynamic", methods=["POST"])
def dynamic_playbook():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    playbook = data.get("playbook") or "playbooks/aggressive.yaml"
    context = data.get("context") or {}
    use_ai = bool(data.get("use_ai", False))
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    path = Path(playbook)
    if not path.is_absolute():
        # Allow "aggressive.yaml" or "playbooks/aggressive.yaml"
        candidate = Path(playbook)
        if candidate.exists():
            path = candidate
        else:
            path = _PLAYBOOK_ROOT / Path(playbook).name
    if not path.exists():
        return jsonify({"error": f"playbook not found: {playbook}"}), 404

    count = DynamicPlaybookCompiler.execute_playbook(
        str(path), session_id, context, use_ai=use_ai
    )
    audit_log(
        "DYNAMIC_PLAYBOOK",
        {"session_id": session_id, "playbook": str(path), "count": count},
    )
    return jsonify({"status": "playbook started", "scheduled": count})


@agg.route("/deception/spawn", methods=["POST"])
def spawn_honeypot():
    data = request.get_json(silent=True) or {}
    service = data.get("service", "http")
    port = int(data.get("port", 8080))
    result = _deception.deploy_honeypot(service, port)
    audit_log("HONEYPOT_SPAWN", result, severity="high")
    return jsonify(result)


@agg.route("/deception/teardown", methods=["POST"])
def teardown_honeypot():
    data = request.get_json(silent=True) or {}
    container_id = data.get("container_id")
    if not container_id:
        return jsonify({"error": "Missing container_id"}), 400
    result = _deception.teardown(container_id)
    return jsonify(result)


@agg.route("/scale/auto", methods=["POST"])
def auto_scale():
    result = _scaler.scale_workers()
    return jsonify({"status": "scaling triggered", **result})


@agg.route("/report/generate", methods=["POST"])
def generate_report():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
    state = get_session_state(session_id)
    if not state:
        return jsonify({"error": "Session not found"}), 404

    prompt = (
        "Write a concise authorized penetration-test report with executive summary, "
        f"findings, and remediation. Data: {json.dumps(state, default=str)[:4000]}"
    )
    report = None
    try:
        from orchestrator.ai import llm

        if llm.llm_configured():
            report = llm.chat_completion(
                [
                    {"role": "system", "content": "You are a security report writer."},
                    {"role": "user", "content": prompt},
                ],
                timeout=60.0,
            )
    except Exception as exc:
        logger.debug("report llm failed: %s", exc)

    if not report:
        try:
            resp = requests.post(
                "http://ollama:11434/api/generate",
                json={"model": "llama3.2", "prompt": prompt, "stream": False},
                timeout=30,
            )
            report = resp.json().get("response")
        except Exception as exc:
            report = f"Unable to generate report ({exc}). Session keys: {list(state.keys())}"

    return jsonify({"report": report})
