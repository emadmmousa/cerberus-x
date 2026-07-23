"""Target surface analysis and adaptive tool selection for chat-driven missions."""

from __future__ import annotations

import re
from typing import Any

# Profile signal → preferred tools (first match wins per category).
_PROFILE_TOOL_MAP: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("wordpress", "wp-content", "wp-includes"), ("nuclei", "nikto", "gobuster", "ffuf", "sqlmap")),
    (("leak", "breach", "paste", "dump"), ("darkweb", "theharvester", "breach_intel")),
    (("login", "signin", "auth", "oauth", "session"), ("sqlmap", "hydra", "ffuf", "xsstrike", "nuclei")),
    (("sqli", "mysql", "postgres", "mssql", "oracle", "mongo"), ("sqlmap", "nuclei", "ffuf", "katana", "darkweb")),
    (("api", "graphql", "rest", "json", "swagger"), ("ffuf", "nuclei", "sqlmap", "katana", "httpx")),
    (("php", "laravel", "drupal", "joomla"), ("nuclei", "nikto", "sqlmap", "gobuster", "ffuf")),
    (("asp", "iis", "dotnet", ".net"), ("nuclei", "nikto", "sqlmap", "nmap", "metasploit")),
    (("cloudflare", "cdn", "akamai", "fastly"), ("httpx", "curlprobe", "nuclei", "nikto", "katana")),
    (("ssh", "sftp"), ("nmap", "hydra", "metasploit", "nuclei")),
    (("smb", "samba", "netbios"), ("crackmapexec", "nmap", "metasploit", "nuclei")),
)

from tools.attack_methods import full_tool_rotation

_DEFAULT_WEB_TOOLS = full_tool_rotation()


def tool_result_failed(item: dict[str, Any]) -> bool:
    """True when a wrapper result indicates the run did not succeed."""
    if not isinstance(item, dict):
        return True
    if item.get("skipped"):
        return True
    err = str(item.get("error") or "").strip()
    if err and not item.get("waf_blocked"):
        return True
    code = item.get("returncode")
    if code not in (None, 0) and not tool_result_productive(item):
        return True
    if item.get("waf_blocked"):
        return False
    if item.get("no_injection_surface"):
        return False
    if item.get("stalled") or item.get("partial"):
        return True
    return False


def tool_result_productive(item: dict[str, Any]) -> bool:
    """True when output advances the engagement (findings, surface, access)."""
    if not isinstance(item, dict):
        return False
    if item.get("vulnerable") or item.get("sessions"):
        return True
    if item.get("waf_blocked"):
        return True
    techs = item.get("technologies")
    if isinstance(techs, list) and techs:
        return True
    if item.get("findings") or item.get("ports") or item.get("directories"):
        return True
    if item.get("results") or item.get("ffuf_finds"):
        return True
    issues = item.get("issues")
    if isinstance(issues, list) and issues:
        return True
    raw = str(item.get("raw_output") or "")
    if re.search(
        r"(?i)\b(vulnerable|CVE-\d{4}-\d+|injection|exploit|shell|session opened|"
        r"valid credentials|\[critical\]|\[high\]|OSVDB)",
        raw,
    ):
        return True
    return False


def phase_tool_outcomes(
    planned_tools: list[dict[str, Any]],
    phase_output: Any,
) -> dict[str, str]:
    """Map each planned tool to outcome: success | failed | unknown."""
    items: list[dict[str, Any]] = []
    if isinstance(phase_output, list):
        items = [i for i in phase_output if isinstance(i, dict)]
    elif isinstance(phase_output, dict):
        items = [phase_output]

    by_tool: dict[str, dict[str, Any]] = {}
    for item in items:
        name = str(item.get("tool") or "").strip().lower()
        if name and name not in by_tool:
            by_tool[name] = item

    outcomes: dict[str, str] = {}
    for entry in planned_tools:
        name = str(entry.get("tool") or "").strip().lower()
        if not name:
            continue
        row = by_tool.get(name, {})
        if tool_result_failed(row):
            outcomes[name] = "failed"
        elif tool_result_productive(row):
            outcomes[name] = "success"
        else:
            outcomes[name] = "success"
    return outcomes


def _text_blob(results_by_phase: dict[str, Any]) -> str:
    chunks: list[str] = []
    for phase_output in (results_by_phase or {}).values():
        rows = phase_output if isinstance(phase_output, list) else [phase_output]
        for item in rows:
            if not isinstance(item, dict):
                continue
            for key in ("raw_output", "error", "tool"):
                val = item.get(key)
                if val:
                    chunks.append(str(val))
            for key in ("findings", "issues", "directories"):
                val = item.get(key)
                if isinstance(val, list):
                    chunks.extend(str(v) for v in val[:20])
    return " ".join(chunks).lower()


def build_target_profile(
    decision_state: dict[str, Any] | None,
    results_by_phase: dict[str, Any] | None,
) -> dict[str, Any]:
    """Summarize technology, surface, and attack hints from prior phases."""
    state = decision_state or {}
    blob = _text_blob(results_by_phase or {})
    signals: list[str] = []

    def _signal(name: str, *needles: str) -> None:
        if any(n in blob for n in needles):
            signals.append(name)

    _signal("wordpress", "wordpress", "wp-content", "wp-includes")
    _signal("php", "php/", "x-powered-by: php", "laravel", "drupal", "joomla")
    _signal("api", "graphql", "swagger", "application/json", "/api/")
    _signal("login", "login", "signin", "sign-in", "password", "oauth")
    _signal("cloudflare", "cloudflare", "cf-ray", "cdn", "akamai")
    _signal("asp", "asp.net", "iis", "microsoft-iis")
    _signal("mysql", "mysql", "mariadb", ":3306", "x-powered-by: mysql")
    _signal("postgres", "postgresql", "postgres", ":5432")
    _signal("mssql", "mssql", "sql server", ":1433", "microsoft sql")
    _signal("oracle", "oracle", "oracledb", ":1521")
    _signal("mongo", "mongodb", ":27017")
    if state.get("sql_injection"):
        signals.append("sqli")
    dbms = str(state.get("sql_dbms") or state.get("dbms") or "").lower()
    if "mysql" in dbms or "mariadb" in dbms:
        signals.append("mysql")
    elif "postgres" in dbms:
        signals.append("postgres")
    elif "mssql" in dbms or "sql server" in dbms:
        signals.append("mssql")
    elif "oracle" in dbms:
        signals.append("oracle")
    open_ports = {str(p) for p in (state.get("open_port_numbers") or [])}
    if open_ports & {"3306"}:
        signals.append("mysql")
    if open_ports & {"5432"}:
        signals.append("postgres")
    if open_ports & {"1433"}:
        signals.append("mssql")
    if open_ports & {"27017"}:
        signals.append("mongo")
    if state.get("http_open"):
        signals.append("web")
    if state.get("ssh_open"):
        signals.append("ssh")
    if state.get("smb_open"):
        signals.append("smb")
    if state.get("directories"):
        signals.append("paths_found")
    if state.get("ffuf_stalled"):
        signals.append("cdn")

    stack = sorted(set(signals))
    return {
        "signals": stack,
        "open_ports": list(state.get("open_port_numbers") or []),
        "directories": len(state.get("directories") or []),
        "http_open": bool(state.get("http_open")),
        "vuln_found": bool(state.get("vuln_found")),
    }


def recommend_attack_tools(
    profile: dict[str, Any],
    allow: set[str],
    *,
    tried: set[str],
    failed: set[str],
) -> list[str]:
    """Order tools by target profile; skip tried/failed names."""
    skip = tried | failed
    ordered: list[str] = []

    for keywords, tools in _PROFILE_TOOL_MAP:
        if not any(sig in profile.get("signals", []) for sig in keywords):
            continue
        for name in tools:
            if name in allow and name not in skip and name not in ordered:
                ordered.append(name)

    if profile.get("http_open") or profile.get("signals"):
        for name in _DEFAULT_WEB_TOOLS:
            if name in allow and name not in skip and name not in ordered:
                ordered.append(name)

    for name in sorted(allow):
        if name not in skip and name not in ordered:
            ordered.append(name)
    return ordered


def build_surface_study_phase(
    target_ctx: dict[str, Any],
    allow: set[str],
) -> dict[str, Any] | None:
    """Deep study: fingerprint every canonical URL variant before attack."""
    tools: list[dict[str, Any]] = []
    variants = list(target_ctx.get("variants") or [])
    https_url = str(target_ctx.get("https_url") or "")
    https_www = str(target_ctx.get("https_www") or "")
    for url in dict.fromkeys([https_url, https_www, *variants[:4]]):
        if not url or "whatweb" not in allow:
            continue
        tools.append({"tool": "whatweb", "args": ["-a", "3", url]})

    for custom in ("httpx", "katana", "curlprobe"):
        if custom not in allow:
            continue
        url = https_www or https_url
        if not url:
            continue
        if custom == "curlprobe":
            tools.append({"tool": custom, "args": ["-sI", "-L", url]})
        elif custom == "httpx":
            tools.append({"tool": custom, "args": []})
        else:
            tools.append({"tool": custom, "args": []})

    if not tools:
        return None
    return {"name": "surface_study", "parallel": True, "tools": tools}
