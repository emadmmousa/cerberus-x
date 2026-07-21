"""Sliver C2 helper — optional binary; no auto-install of a C2 server."""

from __future__ import annotations

import shutil
from typing import Any


def _binary() -> str | None:
    for name in ("sliver-client", "sliver-server", "sliver"):
        path = shutil.which(name)
        if path:
            return path
    return None


def scan(target, args=None) -> dict[str, Any]:
    """Report Sliver availability. Does not generate or deploy payloads here."""
    binary = _binary()
    argv = list(args or [])
    if not binary:
        return {
            "tool": "sliver",
            "target": target,
            "status": "missing_binary",
            "ready": False,
            "error": (
                "sliver-client/sliver-server not installed in this worker image "
                "(optional; install deliberately for authorized C2 work)"
            ),
            "suggested_args": argv or ["--lhost", str(target), "--lport", "443"],
        }

    return {
        "tool": "sliver",
        "target": target,
        "status": "ready",
        "ready": True,
        "binary": binary,
        "note": (
            "Sliver binary found. Use the operator workstation / dedicated C2 host "
            "to generate listeners and payloads; this wrapper only confirms presence."
        ),
        "args": argv,
    }
