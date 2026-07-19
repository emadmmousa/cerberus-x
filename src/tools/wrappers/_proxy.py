"""Shared helpers for attaching proxy metadata and subprocess env."""

from __future__ import annotations

import os
from typing import Any

from tools.proxy_config import credentials_configured, resolve_for_tool


def ensure_worker_proxy(use_proxy: bool) -> None:
    """Start the localhost forwarder on the worker when a proxied scan runs."""
    if not use_proxy or not credentials_configured():
        return
    from tools.local_proxy import ProxyForwardError, ensure_local_proxy

    proxy = ensure_local_proxy()
    if not proxy.healthy():
        raise ProxyForwardError("local proxy forwarder unhealthy")


def proxy_meta(
    tool: str, use_proxy: bool, proxy_protocol: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if use_proxy:
        ensure_worker_proxy(True)
    resolved = resolve_for_tool(tool, use_proxy=use_proxy, protocol=proxy_protocol)
    meta = {
        "enabled": use_proxy,
        "protocol": proxy_protocol,
        "mode": resolved["mode"],
        "note": resolved["note"],
    }
    return resolved, meta


def merge_env(extra: dict[str, str] | None) -> dict[str, str] | None:
    if not extra:
        return None
    env = os.environ.copy()
    env.update(extra)
    return env
