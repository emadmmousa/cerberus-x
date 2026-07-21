"""Blackboard controllers."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from orchestrator.services import blackboard as bb_svc
from security.rbac import Role, require_role

blackboard_bp = Blueprint("blackboard_api", __name__)


@blackboard_bp.get("/api/blackboard/<mission_id>")
@require_role(Role.VIEWER)
def api_blackboard_list(mission_id: str):
    return jsonify(bb_svc.list_docs(mission_id))


@blackboard_bp.route("/api/blackboard/<mission_id>/<path:name>", methods=["GET", "PUT"])
@require_role(Role.VIEWER)
def api_blackboard_key(mission_id: str, name: str):
    if request.method == "GET":
        doc = bb_svc.get_doc(mission_id, name)
        if not doc:
            return jsonify({"error": "not found"}), 404
        return jsonify(doc)
    # PUT requires operator
    from security.rbac import ROLE_RANK, resolve_role, rbac_enforce_enabled

    if rbac_enforce_enabled() and ROLE_RANK[resolve_role()] < ROLE_RANK[Role.OPERATOR]:
        return jsonify({"error": "forbidden", "required": "operator"}), 403
    body = request.get_json(silent=True) or {}
    value = body.get("value")
    ttl = int(body.get("ttl") or 86400)
    expected = body.get("expected_version")
    result = bb_svc.put_doc(
        mission_id,
        name,
        value,
        ttl=ttl,
        expected_version=int(expected) if expected is not None else None,
    )
    return jsonify(result), (200 if result.get("ok") else 409)
