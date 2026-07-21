"""Managed hosting control-plane heartbeat (Firebreak Wave 5)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from security.pro_packaging import managed_hosting_hooks, packaging_status


def heartbeat_payload() -> dict[str, Any]:
    """Payload a managed host would POST to the control plane."""
    hooks = managed_hosting_hooks()
    pkg = packaging_status()
    return {
        "ts": time.time(),
        "edition": pkg.get("edition"),
        "app_base_url": hooks.get("app_base_url"),
        "control_plane_url": hooks.get("control_plane_url"),
        "health_callback_path": hooks.get("health_callback_path"),
        "tenant_header": hooks.get("tenant_header"),
        "managed_hosting_enabled": hooks.get("enabled"),
        "sso_ready": bool((pkg.get("sso") or {}).get("ready")),
        "features": pkg.get("features") or {},
    }


def send_heartbeat(*, timeout: float = 5.0) -> dict[str, Any]:
    """POST heartbeat to FIREBREAK_CONTROL_PLANE_URL when managed hosting is on."""
    hooks = managed_hosting_hooks()
    payload = heartbeat_payload()
    if not hooks.get("enabled"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "managed hosting disabled (set FIREBREAK_EDITION=pro and FIREBREAK_MANAGED_HOSTING=true)",
            "payload": payload,
        }
    control = hooks.get("control_plane_url")
    if not control:
        return {
            "ok": False,
            "skipped": True,
            "reason": "FIREBREAK_CONTROL_PLANE_URL not set",
            "payload": payload,
        }
    url = str(control).rstrip("/") + "/api/v1/agents/heartbeat"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "firebreak-firebreak/1.0",
            "X-Firebreak-Org": os.environ.get("FIREBREAK_ORG_ID") or "default",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")[:2000]
            return {
                "ok": 200 <= resp.status < 300,
                "skipped": False,
                "status": resp.status,
                "url": url,
                "response": raw,
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "skipped": False,
            "status": exc.code,
            "url": url,
            "error": str(exc),
            "payload": payload,
        }
    except Exception as exc:  # noqa: BLE001 — surface network errors to operator
        return {
            "ok": False,
            "skipped": False,
            "url": url,
            "error": str(exc),
            "payload": payload,
        }
