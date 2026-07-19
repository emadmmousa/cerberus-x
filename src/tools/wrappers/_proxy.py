"""Shared helpers for attaching proxy metadata and subprocess env."""

from __future__ import annotations

import os
from typing import Any

from tools.proxy_config import resolve_for_tool


def proxy_meta(tool: str, use_proxy: bool, proxy_protocol: str) -> tuple[dict[str, Any], dict[str, Any]]:
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
