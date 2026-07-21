"""Edition / control-plane controllers."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from security.rbac import Role, require_role

edition_bp = Blueprint("edition_api", __name__)


@edition_bp.get("/api/edition/status")
@require_role(Role.VIEWER)
def api_edition_status():
    from security.pro_packaging import packaging_status

    return jsonify(packaging_status())


@edition_bp.route("/api/edition/heartbeat", methods=["GET", "POST"])
@require_role(Role.ADMIN)
def api_edition_heartbeat():
    from orchestrator.ai.control_plane import heartbeat_payload, send_heartbeat

    if request.method == "GET":
        return jsonify({"payload": heartbeat_payload()})
    result = send_heartbeat()
    code = 200 if result.get("ok") or result.get("skipped") else 502
    return jsonify(result), code
