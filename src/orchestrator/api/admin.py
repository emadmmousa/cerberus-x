"""Admin console controllers: users, orgs, settings, missions ops, logs.

All routes require the ADMIN role when RBAC is enforced. When RBAC is not
enforced (lab default) the decorator is a no-op, so the console is usable
out of the box for self-host.
"""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from security import admin_store
from security.audit import audit_log, recent_audit
from security.rbac import (
    ForbiddenOrg,
    JobNotFound,
    Role,
    job_access_error_response,
    require_role,
)

admin_bp = Blueprint("admin_api", __name__)


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@admin_bp.get("/api/admin/users")
@require_role(Role.ADMIN)
def list_users():
    return jsonify({"users": admin_store.list_users()})


@admin_bp.post("/api/admin/users")
@require_role(Role.ADMIN)
def create_user():
    body = _body()
    try:
        user = admin_store.create_user(
            username=str(body.get("username") or ""),
            password=str(body.get("password") or ""),
            role=str(body.get("role") or "viewer"),
            org_id=str(body.get("org_id") or "default"),
            auth_method=str(body.get("auth_method") or "local"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_USER_CREATE", {"username": user["username"], "role": user["role"]})
    return jsonify({"user": user}), 201


@admin_bp.patch("/api/admin/users/<username>")
@admin_bp.put("/api/admin/users/<username>")
@require_role(Role.ADMIN)
def update_user(username: str):
    body = _body()
    try:
        user = admin_store.update_user(
            username,
            role=body.get("role"),
            org_id=body.get("org_id"),
            auth_method=body.get("auth_method"),
            disabled=body.get("disabled"),
            password=body.get("password"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_USER_UPDATE", {"username": username})
    return jsonify({"user": user})


@admin_bp.delete("/api/admin/users/<username>")
@require_role(Role.ADMIN)
def delete_user(username: str):
    try:
        ok = admin_store.delete_user(username)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": "user not found"}), 404
    audit_log("ADMIN_USER_DELETE", {"username": username}, severity="high")
    return jsonify({"deleted": username})


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------
@admin_bp.get("/api/admin/orgs")
@require_role(Role.ADMIN)
def list_orgs():
    return jsonify({"orgs": admin_store.list_orgs()})


@admin_bp.post("/api/admin/orgs")
@require_role(Role.ADMIN)
def create_org():
    body = _body()
    try:
        org = admin_store.create_org(
            org_id=str(body.get("id") or body.get("org_id") or ""),
            name=str(body.get("name") or ""),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_ORG_CREATE", {"org_id": org["id"]})
    return jsonify({"org": org}), 201


@admin_bp.patch("/api/admin/orgs/<org_id>")
@admin_bp.put("/api/admin/orgs/<org_id>")
@require_role(Role.ADMIN)
def update_org(org_id: str):
    body = _body()
    try:
        org = admin_store.update_org(org_id, name=str(body.get("name") or ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_ORG_UPDATE", {"org_id": org_id})
    return jsonify({"org": org})


@admin_bp.delete("/api/admin/orgs/<org_id>")
@require_role(Role.ADMIN)
def delete_org(org_id: str):
    try:
        ok = admin_store.delete_org(org_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not ok:
        return jsonify({"error": "org not found"}), 404
    audit_log("ADMIN_ORG_DELETE", {"org_id": org_id}, severity="high")
    return jsonify({"deleted": org_id})


@admin_bp.post("/api/admin/orgs/<org_id>/associate")
@require_role(Role.ADMIN)
def associate_user(org_id: str):
    body = _body()
    username = str(body.get("username") or "")
    try:
        user = admin_store.associate_user(username, org_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_ORG_ASSOCIATE", {"org_id": org_id, "username": username})
    return jsonify({"user": user})


# ---------------------------------------------------------------------------
# Settings: RBAC enforce, edition, auth methods
# ---------------------------------------------------------------------------
@admin_bp.get("/api/admin/settings")
@require_role(Role.ADMIN)
def get_settings():
    from orchestrator.ml.flags import (
        effective_auto_scale,
        effective_auto_train,
        effective_learning_tick,
    )
    from security.edition import edition
    from security.pro_packaging import sso_readiness
    from security.rbac import rbac_enforce_enabled

    settings = admin_store.get_settings()
    return jsonify(
        {
            "settings": settings,
            "effective": {
                "rbac_enforce": rbac_enforce_enabled(),
                "edition": edition(),
                "auto_scale": effective_auto_scale(),
                "auto_train": effective_auto_train(),
                "learning_tick": effective_learning_tick(),
            },
            "secret_key_insecure": (
                os.environ.get("SECRET_KEY", "cerberus-x-secret") == "cerberus-x-secret"
            ),
            "options": {
                "editions": list(admin_store.VALID_EDITIONS),
                "roles": list(admin_store.VALID_ROLES),
                "auth_methods": list(admin_store.AUTH_METHODS),
            },
            "sso": sso_readiness(),
        }
    )


@admin_bp.put("/api/admin/settings/rbac")
@require_role(Role.ADMIN)
def set_rbac():
    from flask import session

    from security.pro_packaging import sso_readiness

    body = _body()
    value = body.get("enforce")  # true / false / null (null = defer to env)

    # Lockout guard: enabling enforce requires a way back in. Allow it only when
    # the caller is already an authenticated admin, OR a login path exists
    # (an admin with a password, or SSO configured).
    if value is True and not session.get("user"):
        has_admin_pw = any(
            u.get("role") == "admin" and u.get("has_password")
            for u in admin_store.list_users()
        )
        sso_ready = bool(sso_readiness().get("ready"))
        if not (has_admin_pw or sso_ready):
            return (
                jsonify(
                    {
                        "error": "refused: enabling RBAC enforce would lock you out",
                        "detail": (
                            "Set a password on an admin user or configure SSO "
                            "before enforcing RBAC."
                        ),
                    }
                ),
                409,
            )
    settings = admin_store.set_rbac_enforce(value)
    audit_log("ADMIN_RBAC_SET", {"enforce": value}, severity="high")
    return jsonify({"settings": settings})


@admin_bp.put("/api/admin/settings/edition")
@require_role(Role.ADMIN)
def set_edition():
    body = _body()
    try:
        settings = admin_store.set_edition(body.get("edition"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_EDITION_SET", {"edition": body.get("edition")})
    return jsonify({"settings": settings})


@admin_bp.put("/api/admin/settings/ops")
@require_role(Role.ADMIN)
def set_ops():
    body = _body()
    allowed = {"auto_scale", "auto_train", "learning_tick"}
    unknown = set(body.keys()) - allowed
    if unknown:
        return jsonify({"error": f"unknown keys: {sorted(unknown)}"}), 400
    if not any(k in body for k in allowed):
        return jsonify({"error": "provide at least one ops flag"}), 400
    updated = {}
    try:
        for key in allowed:
            if key not in body:
                continue
            updated[key] = body[key]
            admin_store.set_ops_flag(key, body[key])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_OPS_SET", updated, severity="high")
    return jsonify({"settings": admin_store.get_settings()})


@admin_bp.put("/api/admin/settings/auth")
@require_role(Role.ADMIN)
def set_auth():
    body = _body()
    try:
        settings = admin_store.set_auth_method(
            str(body.get("method") or ""), bool(body.get("enabled"))
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log(
        "ADMIN_AUTH_SET",
        {"method": body.get("method"), "enabled": bool(body.get("enabled"))},
    )
    return jsonify({"settings": settings})


# ---------------------------------------------------------------------------
# Mission control ops
# ---------------------------------------------------------------------------
@admin_bp.patch("/api/admin/missions/<job_id>")
@require_role(Role.OPERATOR)
def edit_mission(job_id: str):
    from orchestrator.services import missions as mission_svc

    try:
        result = mission_svc.edit_mission(job_id, _body())
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    audit_log("MISSION_EDIT", {"job_id": job_id})
    return jsonify(result)


@admin_bp.post("/api/admin/missions/<job_id>/stop")
@require_role(Role.OPERATOR)
def stop_mission(job_id: str):
    from orchestrator.services import missions as mission_svc

    try:
        result = mission_svc.stop_mission(job_id)
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    audit_log("MISSION_STOP", {"job_id": job_id}, severity="high")
    return jsonify(result)


@admin_bp.post("/api/admin/missions/<job_id>/restart")
@require_role(Role.OPERATOR)
def restart_mission(job_id: str):
    from orchestrator.services import missions as mission_svc

    try:
        result = mission_svc.restart_mission(job_id)
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    audit_log("MISSION_RESTART", {"job_id": job_id, "new_id": result.get("task_id")})
    return jsonify(result)


@admin_bp.delete("/api/admin/missions/<job_id>")
@require_role(Role.OPERATOR)
def delete_mission(job_id: str):
    from orchestrator.services import missions as mission_svc

    try:
        ok = mission_svc.delete_mission(job_id)
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    audit_log("MISSION_DELETE", {"job_id": job_id}, severity="high")
    return jsonify({"deleted": job_id, "ok": ok})


# ---------------------------------------------------------------------------
# Logs (audit view)
# ---------------------------------------------------------------------------
@admin_bp.get("/api/admin/logs")
@require_role(Role.ADMIN)
def logs():
    try:
        limit = min(int(request.args.get("limit") or 100), 500)
    except ValueError:
        limit = 100
    event = (request.args.get("event_type") or "").strip()
    actor = (request.args.get("actor") or "").strip()
    rows = recent_audit(limit=limit)
    if event:
        rows = [r for r in rows if r.get("event_type") == event]
    if actor:
        rows = [r for r in rows if str(r.get("actor") or "") == actor]
    rows = list(reversed(rows))  # newest first
    return jsonify({"count": len(rows), "events": rows})
