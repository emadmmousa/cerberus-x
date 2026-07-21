"""BloodHound collection wrapper (bloodhound-python)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _binary() -> str | None:
    for name in ("bloodhound-python", "bloodhound"):
        path = shutil.which(name)
        if path:
            return path
    return None


def scan(target, args=None) -> dict[str, Any]:
    """Run bloodhound-python when credentials/args are provided.

    Without ``-u`` / ``-p`` / ``-d`` (or equivalent), return a structured
    helper result instead of a fake success placeholder.
    """
    binary = _binary()
    if not binary:
        return {
            "tool": "bloodhound",
            "target": target,
            "status": "missing_binary",
            "ready": False,
            "error": (
                "bloodhound-python not found "
                "(pip install bloodhound in the worker image)"
            ),
            "note": "SharpHound.exe on a domain host remains an alternative collector",
        }

    argv = list(args or [])
    joined = " ".join(str(a) for a in argv)
    has_user = any(a in {"-u", "--username"} for a in argv) or "-u " in joined
    has_domain = any(a in {"-d", "--domain"} for a in argv) or "-d " in joined
    if not argv or not (has_user and has_domain):
        return {
            "tool": "bloodhound",
            "target": target,
            "status": "needs_credentials",
            "ready": True,
            "binary": binary,
            "note": (
                "bloodhound-python is installed. Provide domain collection args, e.g. "
                "-u USER -p PASS -d DOMAIN -ns DC --collection All"
            ),
        }

    cmd = [binary, *argv]
    # Ensure a nameserver/target hint when missing.
    if target and not any(a in {"-ns", "--nameserver", "-dc"} for a in argv):
        cmd.extend(["-ns", str(target)])

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        out = ((completed.stdout or "") + (completed.stderr or ""))[:8000]
        result: dict[str, Any] = {
            "tool": "bloodhound",
            "target": target,
            "status": "ok" if completed.returncode == 0 else "error",
            "ready": True,
            "command": " ".join(cmd),
            "returncode": completed.returncode,
            "raw_output": out,
        }
        if completed.returncode != 0:
            result["error"] = f"bloodhound exited with code {completed.returncode}"
        return result
    except subprocess.TimeoutExpired:
        return {
            "tool": "bloodhound",
            "target": target,
            "status": "timeout",
            "ready": True,
            "error": "bloodhound timed out after 300s",
        }
    except FileNotFoundError:
        return {
            "tool": "bloodhound",
            "target": target,
            "status": "missing_binary",
            "ready": False,
            "error": "bloodhound-python not found",
        }
