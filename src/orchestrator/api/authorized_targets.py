"""Authorized-target scope management API."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from scanner.authorization import (
    add_target_entry,
    list_target_entries,
    remove_target_entry,
)
from security.audit import audit_log
from security.rbac import Role, require_role

authorized_targets_bp = Blueprint("authorized_targets_api", __name__)


@authorized_targets_bp.get("/api/authorized-targets")
@require_role(Role.VIEWER)
def list_targets():
    active_only = request.args.get("active", "false").lower() in {"1", "true", "yes"}
    rows = list_target_entries(active_only=active_only)
    return jsonify({"count": len(rows), "targets": rows})


@authorized_targets_bp.post("/api/authorized-targets")
@require_role(Role.OPERATOR)
def add_target():
    body = request.get_json(silent=True) or {}
    target = str(body.get("target") or body.get("host") or body.get("url") or body.get("value") or "").strip()
    kind = str(body.get("kind") or body.get("type") or "").strip().lower() or None
    if not target:
        return jsonify({"error": "target is required"}), 400
    try:
        row = add_target_entry(
            target,
            notes=body.get("notes") or body.get("note"),
            expiry=body.get("expiry"),
            authorized=bool(body.get("authorized", True)),
            kind=kind,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    audit_log("AUTHZ_TARGET_API_ADD", {"target": row.get("target") or target})
    return jsonify({"ok": True, "target": row}), 201


@authorized_targets_bp.delete("/api/authorized-targets/<path:target>")
@require_role(Role.OPERATOR)
def delete_target(target: str):
    try:
        removed = remove_target_entry(target)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 500
    if not removed:
        return jsonify({"error": "not found", "target": target}), 404
    audit_log("AUTHZ_TARGET_API_REMOVE", {"target": target})
    return jsonify({"ok": True, "removed": target})
