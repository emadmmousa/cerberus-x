"""Pro packaging readiness (Firebreak Wave 5 — no paywall on scanning)."""

from __future__ import annotations

import os
from typing import Any

from security.auth0_sdk import auth0_configured, auth0_status
from security.edition import edition, feature_flags, is_pro
from security.oidc import oidc_configured, oidc_status


def sso_readiness() -> dict[str, Any]:
    """Checklist for turnkey SSO packaging (Auth0 preferred)."""
    a0 = auth0_status()
    oidc = oidc_status()
    auth0_ok = auth0_configured()
    oidc_ok = oidc_configured()
    return {
        "ready": auth0_ok or oidc_ok,
        "preferred": "auth0" if auth0_ok else ("oidc" if oidc_ok else None),
        "auth0": {
            "configured": auth0_ok,
            "domain_set": bool(a0.get("domain")),
            "client_id_set": bool(a0.get("client_id_set")),
            "missing": a0.get("missing") or [],
            "login_path": a0.get("login_path"),
            "callback_url": a0.get("callback_url"),
        },
        "oidc": {
            "configured": oidc_ok,
            "issuer": oidc.get("issuer"),
            "client_id_set": bool(oidc.get("client_id_set")),
        },
    }


def managed_hosting_hooks() -> dict[str, Any]:
    """Declarative hooks for a future hosted control plane (env-gated)."""
    base = (os.environ.get("APP_BASE_URL") or "http://localhost:5000").rstrip("/")
    control = (os.environ.get("CERBERUS_CONTROL_PLANE_URL") or "").strip() or None
    return {
        "enabled": is_pro()
        and (os.environ.get("CERBERUS_MANAGED_HOSTING") or "").lower()
        in {"1", "true", "yes", "on"},
        "app_base_url": base,
        "control_plane_url": control,
        "health_callback_path": "/api/edition/status",
        "tenant_header": "X-Cerberus-Org",
    }


def packaging_status() -> dict[str, Any]:
    flags = feature_flags()
    return {
        "edition": edition(),
        "features": flags,
        "sso": sso_readiness(),
        "managed_hosting": managed_hosting_hooks(),
        "notes": (
            "Pro packaging is opt-in via CERBERUS_EDITION=pro; "
            "community keeps all scanning capabilities."
        ),
    }
