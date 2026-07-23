"""When to route mission traffic through the configured upstream proxy."""

from __future__ import annotations

import os
from typing import Any

from tools.proxy_config import credentials_configured


def proxy_default_enabled() -> bool:
    """Default per-run proxy when credentials exist (FIREBREAK_PROXY_DEFAULT)."""
    if not credentials_configured():
        return False
    raw = os.getenv("FIREBREAK_PROXY_DEFAULT", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def resolve_use_proxy(
    *,
    requested: bool | None = None,
    waf_blocked: bool = False,
    cdn: bool = False,
    evasion: str | dict[str, Any] | None = None,
) -> bool:
    """
    Decide whether tools should use the local forwarder → upstream proxy chain.

    Priority:
    1. No credentials → always direct.
    2. WAF/CDN detected → proxy when credentials exist (Cloudflare bypass).
    3. Explicit request True/False from operator.
    4. Aggressive evasion + FIREBREAK_PROXY_DEFAULT.
    """
    if not credentials_configured():
        return False

    if waf_blocked or cdn:
        return True

    if requested is True:
        return True
    if requested is False:
        return False

    level = evasion if isinstance(evasion, str) else (evasion or {}).get("level", "")
    if str(level).lower() in {"aggressive", "high"}:
        return True

    return proxy_default_enabled()


def parse_launch_use_proxy(body: dict[str, Any], *, evasion: str | dict[str, Any] | None = None) -> bool:
    """Read optional use_proxy from a launch payload; apply default policy when omitted."""
    raw = body.get("use_proxy")
    requested = None if raw is None else bool(raw)
    return resolve_use_proxy(requested=requested, evasion=evasion)
