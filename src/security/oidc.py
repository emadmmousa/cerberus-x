"""OIDC / SSO helpers (Firebreak W4.2).

When OIDC_* env vars are set and Authlib is installed, register a provider
and support browser authorize + callback.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional
from urllib.parse import urlencode

from flask import jsonify, redirect, request, session, url_for

from security.audit import audit_log

logger = logging.getLogger(__name__)

_oidc_client = None


def oidc_configured() -> bool:
    return bool(
        (os.environ.get("OIDC_CLIENT_ID") or "").strip()
        and (os.environ.get("OIDC_CLIENT_SECRET") or "").strip()
        and (os.environ.get("OIDC_ISSUER") or "").strip()
    )


def oidc_status() -> dict[str, Any]:
    return {
        "configured": oidc_configured(),
        "issuer": (os.environ.get("OIDC_ISSUER") or "").strip() or None,
        "client_id_set": bool((os.environ.get("OIDC_CLIENT_ID") or "").strip()),
        "scopes": (os.environ.get("OIDC_SCOPES") or "openid profile email").split(),
        "login_path": "/auth/oidc/login",
        "callback_path": "/auth/oidc/callback",
    }


def register_oidc(oauth) -> Optional[Any]:
    """Register Authlib OIDC client if configured. Returns client or None."""
    global _oidc_client
    if not oidc_configured():
        return None
    try:
        client = oauth.register(
            name="oidc",
            client_id=os.environ["OIDC_CLIENT_ID"],
            client_secret=os.environ["OIDC_CLIENT_SECRET"],
            server_metadata_url=os.environ["OIDC_ISSUER"].rstrip("/")
            + "/.well-known/openid-configuration",
            client_kwargs={
                "scope": os.environ.get("OIDC_SCOPES") or "openid profile email",
            },
        )
        _oidc_client = client
        logger.info("OIDC client registered for issuer %s", os.environ.get("OIDC_ISSUER"))
        return client
    except Exception as exc:
        logger.warning("OIDC register failed: %s", exc)
        _oidc_client = None
        return None


def get_oidc_client():
    return _oidc_client


def oidc_login_redirect():
    """Start OIDC authorize redirect, or return JSON error if unavailable."""
    if not oidc_configured():
        return (
            jsonify(
                {
                    "error": "OIDC not configured",
                    "hint": "Set OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ISSUER",
                }
            ),
            503,
        )
    client = _oidc_client
    if client is None:
        # Lazy register against app oauth
        try:
            from security.auth import oauth

            client = register_oidc(oauth)
        except Exception as exc:
            logger.warning("OIDC lazy register failed: %s", exc)
            client = None
    if client is None:
        return (
            jsonify(
                {
                    "error": "OIDC client not registered",
                    "hint": "Install authlib and restart orchestrator",
                    "status": oidc_status(),
                }
            ),
            501,
        )
    redirect_uri = os.environ.get("OIDC_REDIRECT_URI") or url_for(
        "auth.oidc_callback", _external=True
    )
    try:
        return client.authorize_redirect(redirect_uri)
    except Exception as exc:
        logger.warning("OIDC authorize_redirect failed: %s", exc)
        # Fallback: manual authorize URL if metadata has authorization_endpoint
        try:
            meta = getattr(client, "server_metadata", None) or {}
            auth_ep = meta.get("authorization_endpoint")
            if auth_ep:
                params = {
                    "client_id": os.environ["OIDC_CLIENT_ID"],
                    "response_type": "code",
                    "scope": os.environ.get("OIDC_SCOPES") or "openid profile email",
                    "redirect_uri": redirect_uri,
                }
                return redirect(f"{auth_ep}?{urlencode(params)}")
        except Exception:
            pass
        return jsonify({"error": "OIDC redirect failed", "detail": str(exc)}), 501


def oidc_callback_handle():
    """Exchange code for tokens and establish session."""
    if not oidc_configured():
        return jsonify({"error": "OIDC not configured"}), 503
    client = _oidc_client
    if client is None:
        try:
            from security.auth import oauth

            client = register_oidc(oauth)
        except Exception:
            client = None
    if client is None:
        return jsonify({"error": "OIDC client not registered"}), 501
    try:
        token = client.authorize_access_token()
    except Exception as exc:
        audit_log("OIDC_CALLBACK_FAILED", {"error": str(exc)}, severity="high")
        return jsonify({"error": "OIDC token exchange failed", "detail": str(exc)}), 401
    claims = token.get("userinfo") if isinstance(token, dict) else None
    if not claims and isinstance(token, dict):
        claims = token.get("id_token_claims") or {}
    if not isinstance(claims, dict) or not claims:
        # Best-effort userinfo endpoint
        try:
            claims = dict(client.userinfo(token=token))
        except Exception:
            claims = {"sub": "oidc-user"}
    profile = apply_oidc_claims(claims)
    next_url = session.pop("oidc_next", None) or "/"
    wants_json = "application/json" in (request.headers.get("Accept") or "")
    if wants_json:
        return jsonify({"status": "authenticated", **profile, "next": next_url})
    return redirect(next_url)


def apply_oidc_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Map IdP claims → session role / org."""
    email = claims.get("email") or claims.get("preferred_username") or claims.get("sub")
    role = (
        claims.get("firebreak_role")
        or os.environ.get("FIREBREAK_DEFAULT_ROLE")
        or "operator"
    ).lower()
    org = (
        claims.get("org_id")
        or claims.get("org")
        or os.environ.get("FIREBREAK_DEFAULT_ORG")
        or "default"
    )
    session["user"] = email
    session["role"] = role
    session["org_id"] = org
    session["auth_method"] = "oidc"
    audit_log("OIDC_LOGIN", {"user": email, "org_id": org, "role": role})
    return {"user": email, "role": role, "org_id": org}
