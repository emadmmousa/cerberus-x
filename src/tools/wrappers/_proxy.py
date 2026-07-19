"""Shared helpers for attaching proxy metadata and subprocess env."""

from __future__ import annotations

import base64
import os
import socket
from typing import Any
from urllib.parse import urlparse

from tools.proxy_config import credentials_configured, resolve_for_tool, upstream_proxy_url


def ensure_worker_proxy(use_proxy: bool) -> None:
    """Start the localhost forwarder on the worker when a proxied scan runs."""
    if not use_proxy or not credentials_configured():
        return
    from tools.local_proxy import ProxyForwardError, ensure_local_proxy

    proxy = ensure_local_proxy()
    if not proxy.healthy():
        raise ProxyForwardError("local proxy forwarder unhealthy")


def _preflight_upstream_note() -> str | None:
    """Probe Oxylabs CONNECT once; return an operator-facing note on failure."""
    try:
        from tools.proxy_settings import load_credentials

        creds = load_credentials()
        if not creds:
            return "proxy credentials not configured on worker"
        parsed = urlparse(upstream_proxy_url())
        host = parsed.hostname or "pr.oxylabs.io"
        port = parsed.port or 7777
        user = creds["username"]
        password = creds["password"]
        token = base64.b64encode(f"{user}:{password}".encode()).decode()
        sock = socket.create_connection((host, port), timeout=12.0)
        sock.settimeout(12.0)
        try:
            sock.sendall(
                (
                    "CONNECT ip.oxylabs.io:443 HTTP/1.1\r\n"
                    "Host: ip.oxylabs.io:443\r\n"
                    f"Proxy-Authorization: Basic {token}\r\n"
                    "Proxy-Connection: Keep-Alive\r\n"
                    "\r\n"
                ).encode()
            )
            data = b""
            while b"\r\n\r\n" not in data and len(data) < 8192:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        finally:
            sock.close()
        status = data.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
        if " 200 " in status:
            return None
        if " 407 " in status:
            return (
                "oxylabs rejected credentials (407) — refresh "
                "OXYLABS_PROXY_USERNAME/PASSWORD on workers"
            )
        if not status:
            return "oxylabs CONNECT timed out or returned empty response"
        return f"oxylabs CONNECT failed: {status}"
    except Exception as exc:
        return f"oxylabs upstream unreachable: {type(exc).__name__}"


def proxy_meta(
    tool: str, use_proxy: bool, proxy_protocol: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if use_proxy:
        ensure_worker_proxy(True)
    resolved = resolve_for_tool(tool, use_proxy=use_proxy, protocol=proxy_protocol)
    note = resolved["note"]
    if use_proxy and resolved["mode"] == "local_proxy" and note is None:
        note = _preflight_upstream_note()
    meta = {
        "enabled": use_proxy,
        "protocol": proxy_protocol,
        "mode": resolved["mode"],
        "note": note,
    }
    return resolved, meta


def merge_env(extra: dict[str, str] | None) -> dict[str, str] | None:
    if not extra:
        return None
    env = os.environ.copy()
    env.update(extra)
    return env
