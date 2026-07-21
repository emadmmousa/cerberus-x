"""Scaffold / marketplace / AI Lab status controllers."""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from security.rbac import Role, require_role

scaffolds_bp = Blueprint("scaffolds_api", __name__)


@scaffolds_bp.get("/api/scaffolds")
@require_role(Role.VIEWER)
def api_scaffolds():
    from orchestrator.ai import scaffolds

    return jsonify(
        {
            "multi_scaffold": scaffolds.multi_scaffold_enabled(),
            "scaffolds": scaffolds.publish_registry(),
            "health": scaffolds.health_all(),
        }
    )


@scaffolds_bp.route("/api/scaffolds/marketplace", methods=["GET", "POST"])
def api_scaffolds_marketplace():
    from orchestrator.ai.marketplace import marketplace_status, register_scaffold
    from security.rbac import ROLE_RANK, resolve_role, rbac_enforce_enabled

    if request.method == "GET":
        if rbac_enforce_enabled() and ROLE_RANK[resolve_role()] < ROLE_RANK[Role.VIEWER]:
            return jsonify({"error": "forbidden", "required": "viewer"}), 403
        return jsonify(marketplace_status())

    if rbac_enforce_enabled():
        from flask import session

        if not session.get("user") and not session.get("auth_method"):
            return jsonify({"error": "unauthorized"}), 401
        if ROLE_RANK[resolve_role()] < ROLE_RANK[Role.ADMIN]:
            return jsonify({"error": "forbidden", "required": "admin"}), 403
    body = request.get_json(silent=True) or {}
    try:
        row = register_scaffold(body)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "scaffold": row, **marketplace_status()})


@scaffolds_bp.delete("/api/scaffolds/marketplace/<scaffold_id>")
@require_role(Role.ADMIN)
def api_scaffolds_marketplace_delete(scaffold_id: str):
    from orchestrator.ai.marketplace import marketplace_status, unregister_scaffold

    try:
        removed = unregister_scaffold(scaffold_id)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not removed:
        return jsonify({"error": "not found", "id": scaffold_id}), 404
    return jsonify({"ok": True, "removed": scaffold_id, **marketplace_status()})


@scaffolds_bp.get("/api/ai-lab/status")
@require_role(Role.VIEWER)
def api_ai_lab_status():
    from orchestrator.ai import scaffolds
    from security.edition import feature_flags
    from security.pro_packaging import sso_readiness

    return jsonify(
        {
            "model": os.environ.get("FIREBREAK_LLM_MODEL", "firebreak"),
            "base_model": os.environ.get("FIREBREAK_LLM_BASE_MODEL", "qwen2.5:7b"),
            "multi_scaffold": scaffolds.multi_scaffold_enabled(),
            "cost_route": (os.environ.get("FIREBREAK_SCAFFOLD_COST_ROUTE") or "").lower()
            in {"1", "true", "yes", "on"},
            "scaffolds": scaffolds.list_enabled(),
            "edition": feature_flags(),
            "sso": sso_readiness(),
            "waves": {
                "w0_license": True,
                "w1_blackboard": True,
                "w2_training": True,
                "w3_dataset": True,
                "w4_rbac": True,
                "w5_open_core": True,
                "w1_prompt_guard": True,
            },
        }
    )
