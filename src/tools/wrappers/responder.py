"""Responder wrapper — authorized LLMNR/NBT-NS helper."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _binary() -> str | None:
    for name in ("responder", "Responder.py"):
        path = shutil.which(name)
        if path:
            return path
    return None


def scan(target, args=None) -> dict[str, Any]:
    """Probe availability; do not start a long-lived poisoner by default.

    Responder listens on an interface. Running it against a hostname is
    meaningless. Callers that need a live listener must pass args that include
    an interface (``-I`` / ``--interface``) and accept the engagement risk.
    """
    binary = _binary()
    if not binary:
        return {
            "tool": "responder",
            "target": target,
            "status": "missing_binary",
            "ready": False,
            "error": "responder binary not found (install lgandx/Responder in the worker image)",
        }

    argv = list(args or [])
    wants_listen = any(a in {"-I", "--interface"} or str(a).startswith("-I") for a in argv)
    if not wants_listen:
        # Health-style check: binary responds to -h
        try:
            completed = subprocess.run(
                [binary, "-h"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            help_out = (completed.stdout or "") + (completed.stderr or "")
        except Exception as exc:
            return {
                "tool": "responder",
                "target": target,
                "status": "error",
                "ready": False,
                "error": str(exc),
            }
        return {
            "tool": "responder",
            "target": target,
            "status": "ready",
            "ready": True,
            "note": (
                "Responder is installed. Pass -I <iface> to start a listener; "
                "default scan only verifies the binary."
            ),
            "help_excerpt": help_out[:400],
        }

    # Short bounded run so the worker cannot hang forever.
    cmd = [binary, *argv]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "tool": "responder",
            "target": target,
            "status": "ran",
            "ready": True,
            "command": " ".join(cmd),
            "returncode": completed.returncode,
            "raw_output": ((completed.stdout or "") + (completed.stderr or ""))[:4000],
        }
    except subprocess.TimeoutExpired as exc:
        out = ""
        if isinstance(exc.stdout, bytes):
            out += exc.stdout.decode("utf-8", errors="replace")
        elif exc.stdout:
            out += str(exc.stdout)
        if isinstance(exc.stderr, bytes):
            out += exc.stderr.decode("utf-8", errors="replace")
        elif exc.stderr:
            out += str(exc.stderr)
        return {
            "tool": "responder",
            "target": target,
            "status": "timeout",
            "ready": True,
            "command": " ".join(cmd),
            "note": "Listener started then stopped after 30s bound",
            "raw_output": out[:4000],
        }
    except FileNotFoundError:
        return {
            "tool": "responder",
            "target": target,
            "status": "missing_binary",
            "ready": False,
            "error": "responder binary not found",
        }
