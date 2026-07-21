"""Auth0 official SDK integration (Regular Web App, server-side).

Uses auth0-server-python ServerClient — do not hand-roll OAuth/OIDC.
Secrets come from environment variables only (never log them).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from flask import after_this_request, request, session

logger = logging.getLogger(__name__)

_client: Any = None


def auth0_configured() -> bool:
    return bool(
        (os.environ.get("AUTH0_DOMAIN") or "").strip()
        and (os.environ.get("AUTH0_CLIENT_ID") or "").strip()
        and (os.environ.get("AUTH0_CLIENT_SECRET") or "").strip()
        and (os.environ.get("AUTH0_SECRET") or "").strip()
    )


def auth0_status() -> dict[str, Any]:
    base = (os.environ.get("APP_BASE_URL") or "http://localhost:5000").rstrip("/")
    required = (
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
        "AUTH0_SECRET",
    )
    missing = [k for k in required if not (os.environ.get(k) or "").strip()]
    return {
        "provider": "auth0",
        "configured": auth0_configured(),
        "domain": (os.environ.get("AUTH0_DOMAIN") or "").strip() or None,
        "client_id_set": bool((os.environ.get("AUTH0_CLIENT_ID") or "").strip()),
        "missing": missing,
        "login_path": "/auth/sso",
        "callback_path": "/callback",
        "logout_path": "/logout",
        "callback_url": f"{base}/callback",
        "logout_url": base,
        "app_base_url": base,
    }


def _make_cookie_store(secret: str, cookie_name: str, max_age: int, model):
    from auth0_server_python.store.abstract import AbstractDataStore

    class CookieStoreImpl(AbstractDataStore):
        def __init__(self):
            super().__init__({"secret": secret})
            self.cookie_name = cookie_name
            self.max_age = max_age
            self.model = model

        async def set(self, identifier, state, **_):
            @after_this_request
            def apply(response):
                data = state.model_dump() if hasattr(state, "model_dump") else state
                response.set_cookie(
                    self.cookie_name,
                    self.encrypt(identifier, data),
                    httponly=True,
                    samesite="Lax",
                    secure=not (
                        os.environ.get("APP_BASE_URL") or "http://"
                    ).startswith("http://"),
                    max_age=self.max_age,
                )
                return response

        async def get(self, identifier, options=None):
            try:
                req = (options or {}).get("request") or request
                encrypted = req.cookies.get(self.cookie_name)
                if not encrypted:
                    return None
                return self.model.model_validate(self.decrypt(identifier, encrypted))
            except Exception:
                logger.warning(
                    "Failed to decrypt Auth0 cookie %s", self.cookie_name, exc_info=True
                )
                return None

        async def delete(self, *_, **__):
            @after_this_request
            def apply(response):
                response.delete_cookie(self.cookie_name)
                return response

    return CookieStoreImpl()


def build_auth0_client():
    """Build Auth0 ServerClient from env. Raises if not configured."""
    from auth0_server_python.auth_server.server_client import ServerClient
    from auth0_server_python.auth_types import StateData, TransactionData

    if not auth0_configured():
        raise RuntimeError("Auth0 is not configured")

    session_secret = os.environ["AUTH0_SECRET"]
    base = (os.environ.get("APP_BASE_URL") or "http://localhost:5000").rstrip("/")
    return ServerClient(
        domain=os.environ["AUTH0_DOMAIN"],
        client_id=os.environ["AUTH0_CLIENT_ID"],
        client_secret=os.environ["AUTH0_CLIENT_SECRET"],
        redirect_uri=f"{base}/callback",
        authorization_params={"scope": "openid profile email"},
        secret=session_secret,
        state_store=_make_cookie_store(session_secret, "_a0_session", 259200, StateData),
        transaction_store=_make_cookie_store(
            session_secret, "_a0_tx", 300, TransactionData
        ),
    )


def get_auth0_client():
    global _client
    if _client is None:
        _client = build_auth0_client()
    return _client


def reset_auth0_client() -> None:
    """Test helper: drop cached client."""
    global _client
    _client = None


def sync_flask_session_from_user(user: Optional[dict[str, Any]]) -> None:
    """Bridge Auth0 user profile into Firebreak Flask session (RBAC / UI)."""
    if not user:
        return
    email = user.get("email") or user.get("nickname") or user.get("sub") or "auth0-user"
    session["user"] = email
    session["auth_method"] = "auth0"
    session["role"] = (
        user.get("firebreak_role")
        or os.environ.get("FIREBREAK_DEFAULT_ROLE")
        or "operator"
    ).lower()
    session["org_id"] = (
        user.get("org_id") or os.environ.get("FIREBREAK_DEFAULT_ORG") or "default"
    )
    session["auth0_sub"] = user.get("sub")
