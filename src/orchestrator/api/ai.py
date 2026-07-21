"""AI plan / session controllers."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from security.rbac import Role, require_role

ai_bp = Blueprint("ai_api", __name__)


@ai_bp.get("/api/ai/sessions")
@require_role(Role.VIEWER)
def api_ai_sessions():
    from orchestrator.mcp import sessions as mcp_sessions

    return jsonify({"sessions": mcp_sessions.list_sessions(limit=50)})


@ai_bp.get("/api/ai/audit/<session_id>")
@require_role(Role.VIEWER)
def api_ai_audit(session_id: str):
    from orchestrator.mcp import sessions as mcp_sessions

    return jsonify(
        {
            "session_id": session_id,
            "audit": mcp_sessions.list_audit(session_id, limit=100),
        }
    )


@ai_bp.post("/api/ai/plan")
@require_role(Role.OPERATOR)
def api_ai_plan():
    body = request.get_json(silent=True) or {}
    target = (body.get("target") or "").strip()
    if not target:
        return jsonify({"error": "target is required"}), 400
    from orchestrator.ai import planner

    plan = planner.suggest_next_phase(
        target,
        body.get("results") if isinstance(body.get("results"), dict) else {},
        nl_goal=str(body.get("nl_goal") or ""),
        step=int(body.get("step") or 0),
        posture=str(body.get("posture") or "balanced"),
    )
    return jsonify(plan)
