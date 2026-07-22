"""OAuth / LDAP / local authentication routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from security.auth import AuthManager

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login/<provider>")
def login(provider: str):
    if provider not in {"google", "github"}:
        return jsonify({"error": "Provider not supported"}), 400
    return AuthManager.oauth_login(provider)


@auth_bp.route("/oauth-callback/<provider>")
def oauth_callback(provider: str):
    return AuthManager.oauth_callback(provider)


@auth_bp.route("/ldap/login", methods=["POST"])
def ldap_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
    return AuthManager.ldap_login(username, password)


@auth_bp.route("/local/login", methods=["POST"])
def local_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
    return AuthManager.local_login(username, password)


@auth_bp.route("/local/signup", methods=["POST"])
def local_signup():
    """Self-service signup: create an isolated tenant org + operator, then log in."""
    import re as _re

    from security import admin_store
    from security.audit import audit_log

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    org_name = (data.get("org") or data.get("company") or "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if admin_store.get_user(username):
        return jsonify({"error": "An account with that username already exists"}), 409

    base_slug = (
        _re.sub(r"[^a-z0-9]+", "-", (org_name or username).lower()).strip("-") or "org"
    )
    existing = {o["id"] for o in admin_store.list_orgs()}
    org_id, suffix = base_slug, 1
    while org_id in existing:
        suffix += 1
        org_id = f"{base_slug}-{suffix}"

    try:
        admin_store.create_org(org_id=org_id, name=org_name or username)
        admin_store.create_user(
            username=username,
            password=password,
            role="operator",
            org_id=org_id,
            auth_method="local",
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    session.clear()
    session["user"] = username
    session["auth_method"] = "local"
    session["role"] = "operator"
    session["org_id"] = org_id
    audit_log("SIGNUP_SUCCESS", {"user": username, "org_id": org_id})
    return (
        jsonify(
            {
                "status": "authenticated",
                "user": username,
                "role": "operator",
                "org_id": org_id,
            }
        ),
        201,
    )


@auth_bp.route("/oidc/status")
def oidc_status_route():
    from security.oidc import oidc_status

    return jsonify(oidc_status())


@auth_bp.route("/oidc/login")
def oidc_login():
    from security.oidc import oidc_login_redirect

    next_url = request.args.get("next") or "/"
    session["oidc_next"] = next_url
    return oidc_login_redirect()


@auth_bp.route("/oidc/callback")
def oidc_callback():
    from security.oidc import oidc_callback_handle

    return oidc_callback_handle()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "logged out"})


@auth_bp.route("/status")
def auth_status():
    # Prefer Auth0 SDK session when configured.
    try:
        import asyncio

        from security.auth0_sdk import (
            auth0_configured,
            get_auth0_client,
            sync_flask_session_from_user,
        )

        if auth0_configured():
            user = asyncio.run(get_auth0_client().get_user({"request": request}))
            if user:
                sync_flask_session_from_user(user if isinstance(user, dict) else None)
                return jsonify(
                    {
                        "authenticated": True,
                        "user": session.get("user"),
                        "role": session.get("role"),
                        "org_id": session.get("org_id"),
                        "auth_method": "auth0",
                        "profile": {
                            "email": user.get("email") if isinstance(user, dict) else None,
                            "sub": user.get("sub") if isinstance(user, dict) else None,
                            "name": user.get("name") if isinstance(user, dict) else None,
                        },
                    }
                )
    except Exception:
        pass

    if "user" in session:
        return jsonify(
            {
                "authenticated": True,
                "user": session["user"],
                "role": session.get("role"),
                "org_id": session.get("org_id"),
                "auth_method": session.get("auth_method"),
            }
        )
    return jsonify({"authenticated": False})
