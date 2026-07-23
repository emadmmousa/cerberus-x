"""Central defaults and argv normalization for all registered scan tools."""

from __future__ import annotations

from typing import Sequence
from urllib.parse import urlparse

from tools.wrappers._argv import coerce_argv
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TOOL_ARGS: dict[str, list[str]] = {
    "rustscan": ["--ulimit", "5000", "--top"],
    "nmap": ["-sV", "-T4"],
    "masscan": ["-p80,443,22,8080,8443", "--rate=1000", "--wait=0"],
    "whatweb": ["-a", "3"],
    "nuclei": ["-t", "http/cves/", "-severity", "critical,high", "-silent"],
    "nikto": ["-maxtime", "120"],
    "ffuf": ["-ac"],
    "gobuster": ["dir", "-w", "/usr/share/dirb/wordlists/common.txt"],
    "sqlmap": ["--batch", "--forms", "--crawl=2", "--level=3", "--risk=2"],
    "xsstrike": ["--timeout", "20", "--skip"],
    "hydra": [],
    "metasploit": ["auxiliary/scanner/portscan/tcp"],
    "theharvester": ["-b", "crtsh"],
    "subfinder": ["-silent"],
    "gau": ["--subs"],
    "sherlock": ["--print-found", "--no-color"],
    "katana": ["-d", "3", "-jc", "-silent"],
    "httpx": ["-silent", "-status-code", "-title", "-tech-detect"],
    "whatweb": ["-a", "3"],
    "darkweb": ["--method", "full"],
    "breach_intel": ["--limit", "25"],
    "crackmapexec": [],
    "impacket": [],
    "zmap": ["-p", "80,443,22"],
    "john": [],
    "hashcat": [],
    "winpeas": [],
    "linpeas": [],
    "responder": [],
    "bloodhound": [],
    "sliver": [],
    "feroxbuster": ["-q"],
    "naabu": ["-silent"],
    "dnsx": ["-silent"],
    "amass": ["enum", "-passive"],
    "dalfox": ["--silence"],
    "waybackurls": [],
    "sslscan": [],
    "arjun": ["--stable"],
    "enum4linux": ["-A"],
    "commix": ["--batch"],
    "wpscan": ["--no-update", "--random-user-agent"],
}


def default_args_for(tool: str) -> list[str]:
    """Return a copy of the default argv for a tool (may be empty)."""
    return list(DEFAULT_TOOL_ARGS.get((tool or "").strip().lower(), []))


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _domain(target: str) -> str:
    return _host(target)


def _web_url(target: str) -> str:
    if not (target or "").strip():
        return target
    return canonicalize_web_url(target, probe=False)


def _strip_osint_seed_args(args: list[str]) -> list[str]:
    argv = list(args)
    out: list[str] = []
    skip_next = False
    for token in argv:
        if skip_next:
            skip_next = False
            continue
        if token in {"--seeds", "--osint-seeds"}:
            skip_next = True
            continue
        out.append(token)
    return out


def _theharvester_args(target: str, args: list[str]) -> list[str]:
    domain = _domain(target)
    cleaned = _strip_osint_seed_args(list(args))
    if not cleaned:
        return ["-d", domain, "-l", "100", "-b", "crtsh"]
    normalized = list(cleaned)
    if "-d" in normalized:
        idx = normalized.index("-d")
        if idx + 1 < len(normalized):
            normalized[idx + 1] = _domain(str(normalized[idx + 1]))
    else:
        normalized = ["-d", domain, *normalized]
    if "-b" in normalized:
        idx = normalized.index("-b")
        if idx + 1 < len(normalized) and str(normalized[idx + 1]).lower() in {
            "google",
            "bing",
            "yahoo",
        }:
            normalized[idx + 1] = "crtsh"
    return normalized


def _impacket_args(target: str, args: list[str]) -> list[str]:
    host = _host(target)
    if not args:
        return [host]
    return [
        arg.replace("{{target}}", host) if isinstance(arg, str) else str(arg)
        for arg in args
    ]


def _crackmapexec_args(target: str, args: list[str]) -> list[str]:
    from tools.wrappers.crackmapexec import _normalize_args

    host = _host(target)
    if not args:
        return ["smb", host, "-u", "guest", "-p", "", "--shares"]
    return _normalize_args(args, host)


def _metasploit_args(args: list[str]) -> list[str]:
    from tools.wrappers.metasploit import DEFAULT_MODULE, normalize_module_path

    if not args:
        return [DEFAULT_MODULE]
    normalized = list(args)
    try:
        normalized[0] = normalize_module_path(str(normalized[0]))
    except ValueError:
        normalized[0] = DEFAULT_MODULE
    return normalized


def normalize_tool_args(
    tool: str,
    target: str,
    args: Sequence | None = None,
    *,
    evasion: dict | None = None,
) -> list[str]:
    """
    Apply playbook defaults and tool-specific sanitizers before Celery dispatch.

    Empty or missing args receive DEFAULT_TOOL_ARGS. Each wrapper's existing
    sanitize logic is reused so LLM-invented flags are corrected consistently.
    """
    if evasion is None:
        evasion = {}

    name = (tool or "").strip().lower()
    raw = coerce_argv(args)
    if not raw:
        raw = default_args_for(name)

    replaced = [
        arg.replace("{{target}}", target) if isinstance(arg, str) else str(arg)
        for arg in raw
    ]

    if name == "masscan":
        from tools.wrappers import masscan

        return masscan.sanitize_args(replaced)

    if name == "nmap":
        from tools.wrappers import nmap

        return nmap.sanitize_args(replaced)

    if name == "gobuster":
        from tools.wrappers import gobuster

        url = _web_url(target) if target else None
        return gobuster.sanitize_args(replaced, url=url)

    if name == "nuclei":
        from tools.wrappers import nuclei

        return nuclei._normalize_args(replaced, evasion)

    if name == "ffuf":
        from tools.wrappers import ffuf

        url = _web_url(target) if target else target
        return ffuf._normalize_args(replaced, url, evasion)

    if name == "nikto":
        from tools.wrappers import nikto

        url = _web_url(target) if target else target
        return nikto._normalize_args(url, replaced, evasion)

    if name == "xsstrike":
        from tools.wrappers import xsstrike

        return xsstrike._normalize_args(replaced, evasion)

    if name == "metasploit":
        return _metasploit_args(replaced)

    if name == "rustscan":
        from tools.wrappers import rustscan

        host = _host(target) if target else ""
        if host:
            replaced = rustscan._ensure_address(replaced, host)
        return rustscan._ensure_quiet_flags(replaced)

    if name == "theharvester":
        return _theharvester_args(target, replaced)

    if name in {"subfinder", "gau", "sherlock", "darkweb", "breach_intel", "katana", "httpx", "whatweb"}:
        return _strip_osint_seed_args(replaced)

    if name == "sqlmap":
        if "--batch" not in replaced and "-b" not in replaced:
            replaced = ["--batch", *replaced]
        return replaced

    if name == "crackmapexec":
        return _crackmapexec_args(target, replaced)

    if name == "impacket":
        return _impacket_args(target, replaced)

    if name == "whatweb" and not replaced:
        return ["-a", "3"]

    if name == "zmap" and not replaced:
        return ["-p", "80,443,22"]

    return replaced
