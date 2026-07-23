"""Shared subprocess runner for thin CLI tool wrappers."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable
from urllib.parse import urlparse

from tools.wrappers._web_url import canonicalize_web_url


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    return (parsed.hostname or parsed.path.split("/")[0] or target).strip("[]")


def _web_url(target: str) -> str:
    if not (target or "").strip():
        return target
    return canonicalize_web_url(target, probe=False)


def default_timeout(tool_name: str, fallback: int = 120) -> int:
    raw = os.environ.get(f"FIREBREAK_{tool_name.upper()}_TIMEOUT", str(fallback))
    try:
        return max(30, int(raw))
    except ValueError:
        return fallback


def generic_cli_scan(
    tool_name: str,
    target: str,
    args=None,
    evasion=None,
    *,
    binary: str | None = None,
    default_argv: list[str] | None = None,
    build_argv: Callable[[str, list[str], str, str], list[str]] | None = None,
    timeout: int | None = None,
    parse_output: Callable[[str], dict] | None = None,
) -> dict:
    """Run a CLI binary and return a normalized mission result dict."""
    del evasion
    cli_args = list(args or [])
    host = _host(target)
    url = _web_url(target)
    bin_name = binary or tool_name
    exe = shutil.which(bin_name) or bin_name

    if build_argv is not None:
        argv = build_argv(host, cli_args, url, target)
    else:
        argv = [exe, *(cli_args or default_argv or [target])]

    if argv and argv[0] != exe and not os.path.isabs(argv[0]):
        argv[0] = exe

    wall = timeout if timeout is not None else default_timeout(tool_name)
    cmd = argv
    try:
        output = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=wall,
        )
        parsed = parse_output(output) if parse_output else {}
        return {
            "tool": tool_name,
            "target": target,
            "argv": cmd,
            "raw_output": output[:20000],
            "productive": bool(output.strip()),
            **parsed,
        }
    except FileNotFoundError:
        return {
            "tool": tool_name,
            "target": target,
            "error": f"{bin_name} is not installed",
            "productive": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": tool_name,
            "target": target,
            "error": f"{tool_name} timed out after {wall}s",
            "partial": True,
            "productive": False,
        }
    except subprocess.CalledProcessError as exc:
        out = (exc.output or "")[:20000]
        parsed = parse_output(out) if parse_output and out else {}
        return {
            "tool": tool_name,
            "target": target,
            "error": str(exc.output or exc)[:500],
            "raw_output": out,
            "productive": bool(out.strip()),
            **parsed,
        }
