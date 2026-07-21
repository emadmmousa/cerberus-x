"""Auth0 Regular Web App routes using the official auth0-server-python SDK."""

from __future__ import annotations

import asyncio
import logging
import os

from flask import Blueprint, jsonify, redirect, request, session

logger = logging.getLogger(__name__)

auth0_bp = Blueprint("auth0", __name__)


def _run(coro):
    """Run Auth0 SDK async APIs from sync Flask views."""
    return asyncio.run(coro)


@auth0_bp.route("/auth/sso")
def auth0_login():
    """Start Auth0 interactive login (SPA Login page owns /login)."""
    from security.auth0_sdk import auth0_configured, get_auth0_client

    if not auth0_configured():
        return (
            jsonify(
                {
                    "error": "Auth0 not configured",
                    "hint": "Set AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_SECRET, APP_BASE_URL in .env (see docs/AUTH0_SETUP.md)",
                }
            ),
            503,
        )
    from auth0_server_python.auth_types import StartInteractiveLoginOptions

    client = get_auth0_client()
    url = _run(
        client.start_interactive_login(
            options=StartInteractiveLoginOptions(
                authorization_params=dict(request.args),
            ),
            store_options={"request": request},
        )
    )
    return redirect(url)


@auth0_bp.route("/callback")
def auth0_callback():
    from security.auth0_sdk import (
        auth0_configured,
        get_auth0_client,
        sync_flask_session_from_user,
    )
    from security.audit import audit_log

    if not auth0_configured():
        return jsonify({"error": "Auth0 not configured"}), 503
    client = get_auth0_client()
    try:
        _run(
            client.complete_interactive_login(
                url=request.url,
                store_options={"request": request},
            )
        )
        user = _run(client.get_user({"request": request}))
        sync_flask_session_from_user(user if isinstance(user, dict) else None)
        audit_log(
            "AUTH0_LOGIN",
            {"user": session.get("user"), "org_id": session.get("org_id")},
        )
        return redirect("/missions")
    except Exception:
        logger.exception("Auth0 callback error")
        audit_log("AUTH0_CALLBACK_FAILED", {"path": request.path}, severity="high")
        return "Auth0 callback failed. Check orchestrator logs.", 400


@auth0_bp.route("/logout")
def auth0_logout():
    from security.auth0_sdk import auth0_configured, get_auth0_client

    if not auth0_configured():
        session.clear()
        return redirect("/")
    from auth0_server_python.auth_types import LogoutOptions

    client = get_auth0_client()
    base = (os.environ.get("APP_BASE_URL") or "http://localhost:5000").rstrip("/")
    try:
        url = _run(
            client.logout(
                options=LogoutOptions(return_to=base),
                store_options={"request": request},
            )
        )
    except Exception:
        logger.exception("Auth0 logout error")
        session.clear()
        return redirect("/")
    session.clear()
    return redirect(url)
