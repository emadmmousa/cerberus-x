"""Self-service profile endpoints (username, password, org display name)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from security.audit import audit_log
from security.rbac import require_auth

profile_bp = Blueprint("profile_api", __name__)

USERNAME_MIN = 3
PASSWORD_MIN = 8


def _session_user() -> str | None:
    user = (session.get("user") or "").strip()
    return user or None


def _session_profile_fallback() -> dict:
    user = _session_user() or ""
    auth_method = session.get("auth_method")
    return {
        "username": user,
        "role": session.get("role"),
        "org_id": session.get("org_id"),
        "auth_method": auth_method,
        "disabled": False,
        "has_password": False,
        "can_edit_username": False,
        "can_edit_password": False,
        "can_edit_org_name": False,
        "managed_externally": auth_method not in (None, "local"),
    }


@profile_bp.get("/api/profile/me")
@require_auth()
def profile_me():
    user = _session_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    from security import admin_store

    profile = admin_store.get_profile_payload(user)
    if profile:
        return jsonify(profile)
    return jsonify(_session_profile_fallback())


@profile_bp.get("/api/profile/username/check")
@require_auth()
def profile_username_check():
    user = _session_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    username = (request.args.get("username") or "").strip()
    if len(username) < USERNAME_MIN:
        return jsonify(
            {
                "available": False,
                "username": username,
                "reason": f"Username must be at least {USERNAME_MIN} characters",
            }
        )

    from security import admin_store

    profile = admin_store.get_profile_payload(user)
    if profile and not profile.get("can_edit_username"):
        return jsonify(
            {
                "available": False,
                "username": username,
                "reason": "Username is managed by your identity provider",
            }
        )

    available = admin_store.username_available(username, exclude=user)
    return jsonify({"available": available, "username": username})


@profile_bp.patch("/api/profile")
@require_auth()
def profile_update():
    user = _session_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_username = (data.get("username") or "").strip() or None
    new_password = data.get("new_password") or None
    org_name = data.get("org_name")
    if org_name is not None:
        org_name = str(org_name).strip()

    if not current_password:
        return jsonify({"error": "Current password is required"}), 400
    if new_username and len(new_username) < USERNAME_MIN:
        return jsonify({"error": f"Username must be at least {USERNAME_MIN} characters"}), 400
    if new_password and len(new_password) < PASSWORD_MIN:
        return jsonify({"error": f"Password must be at least {PASSWORD_MIN} characters"}), 400
    if not any([new_username, new_password, org_name is not None]):
        return jsonify({"error": "No profile changes requested"}), 400

    from security import admin_store

    profile = admin_store.get_profile_payload(user)
    if not profile:
        return jsonify({"error": "Profile is managed by your identity provider"}), 400
    if new_username and not profile.get("can_edit_username"):
        return jsonify({"error": "Username cannot be changed for this account"}), 400
    if new_password and not profile.get("can_edit_password"):
        return jsonify({"error": "Password cannot be changed for this account"}), 400
    if org_name is not None and not profile.get("can_edit_org_name"):
        return jsonify({"error": "Organization name cannot be changed"}), 400

    try:
        updated = admin_store.update_self_profile(
            user,
            current_password=current_password,
            new_username=new_username,
            new_password=new_password,
            org_name=org_name,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    new_user = updated.get("username") or user
    if new_user != user:
        session["user"] = new_user
    audit_log(
        "PROFILE_UPDATED",
        {
            "user": new_user,
            "username_changed": new_user != user,
            "password_changed": bool(new_password),
            "org_name_changed": org_name is not None,
        },
    )
    return jsonify(updated)
