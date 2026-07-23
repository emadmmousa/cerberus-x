"""ProjectDiscovery httpx probe (not the Python httpx HTTP client)."""

from __future__ import annotations

import os
import re
import subprocess

from tools.osint_scrape import parse_seeds, pick_web_url, skip_result, strip_osint_seed_args
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_HTTPX_TIMEOUT", "60"))
_PD_HTTPX_BIN = os.environ.get("FIREBREAK_PD_HTTPX_BIN", "pd-httpx")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_SKIP_TECH = frozenset(
    {
        "country",
        "ip",
        "email",
        "uncommonheaders",
        "open-graph-protocol",
        "title",
    }
)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _resolve_binary() -> str:
    for candidate in (_PD_HTTPX_BIN, "pd-httpx", "/usr/local/bin/pd-httpx"):
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return _PD_HTTPX_BIN


def _parse_line(line: str) -> dict[str, object]:
    clean = _strip_ansi(line).strip()
    if not clean or clean.lower().startswith("usage:"):
        return {}
    url_match = re.match(r"(https?://\S+)", clean)
    if not url_match:
        return {}
    url = url_match.group(1)
    groups = re.findall(r"\[([^\[\]]+)\]", clean)
    status_code = None
    title = None
    tech_blob = ""
    if groups:
        if groups[0].strip().isdigit():
            status_code = groups[0].strip()
            groups = groups[1:]
        if len(groups) >= 2:
            title = groups[0].strip()
            tech_blob = groups[1].strip()
        elif len(groups) == 1:
            if "," in groups[0]:
                tech_blob = groups[0].strip()
            else:
                title = groups[0].strip()

    technologies: list[str] = []
    if tech_blob:
        for token in tech_blob.split(","):
            name = token.strip()
            if name and name.lower() not in _SKIP_TECH:
                technologies.append(name)

    payload: dict[str, object] = {"url": url}
    if status_code:
        payload["status_code"] = status_code
    if title:
        payload["title"] = title
    if technologies:
        payload["technologies"] = technologies
    return payload


def scan(
    target,
    args=None,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion=None,
    timeout: int | None = None,
):
    del use_proxy, proxy_protocol, evasion  # direct probe; proxy wiring can follow ffuf pattern
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    url = pick_web_url(target, seeds)
    if not url:
        return skip_result(
            "httpx",
            target,
            seeds=seeds,
            note="HTTP probing requires a domain, URL, or social profile seed.",
        )
    url = canonicalize_web_url(url)
    binary = _resolve_binary()
    wall_timeout = timeout or DEFAULT_TIMEOUT_SECONDS
    cmd = [
        binary,
        "-u",
        url,
        "-silent",
        "-status-code",
        "-title",
        "-tech-detect",
        "-follow-redirects",
        *(list(cli_args) if cli_args else []),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=wall_timeout,
            start_new_session=True,
            check=False,
        )
        output = _strip_ansi((completed.stdout or "") + (completed.stderr or ""))
        if completed.returncode != 0 and "No such option" in output:
            return {
                "tool": "httpx",
                "target": url,
                "error": (
                    "wrong httpx binary on PATH (Python httpx client). "
                    "Install ProjectDiscovery httpx as pd-httpx on workers."
                ),
                "raw_output": output.strip(),
                "returncode": completed.returncode,
                "argv": cmd,
            }
        parsed = {}
        for line in output.splitlines():
            row = _parse_line(line)
            if row:
                parsed = row
                break
        payload: dict[str, object] = {
            "tool": "httpx",
            "target": url,
            "raw_output": output.strip(),
            "returncode": completed.returncode,
            "argv": cmd,
        }
        payload.update(parsed)
        if completed.returncode != 0 and not output.strip():
            payload["error"] = f"httpx exited with code {completed.returncode}"
        return payload
    except FileNotFoundError:
        return {
            "tool": "httpx",
            "target": url,
            "error": f"ProjectDiscovery httpx binary not found ({binary})",
            "argv": cmd,
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": "httpx",
            "target": url,
            "error": f"httpx timed out after {wall_timeout}s",
            "partial": True,
            "argv": cmd,
        }
