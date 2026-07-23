"""Invent novel attack wrappers when standard tools fail to meet the mission goal."""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_INVENTION_SYSTEM = """You are Firebreak's adaptive attack engineer on an AUTHORIZED engagement.
Standard scanners failed or produced nothing useful. Invent ONE new custom wrapper that uses
real CLI binaries already on a typical Kali worker (curl, ffuf, nmap, python3, etc.).

When the goal involves DATABASE ACCESS, SQL injection, or data exfiltration, prioritize:
- Error/time-based SQLi probes via curl (inject into id, q, page, user, search params)
- GraphQL/JSON API injection probes (Content-Type application/json)
- Backup/dump path checks (/backup.sql, /.env, /db.sql, /adminer.php, /phpmyadmin/)
- Header-based SQLi (X-Forwarded-For, Referer, User-Agent)
- Second-order style probes (register/search then revisit)

Return ONLY JSON:
{
  "name": "lowercase_tool_name",
  "binary": "single_path_executable",
  "args_template": ["tokens", "with", "{url}", "{domain}", "{target}", "{args}"],
  "description": "one line",
  "risk": "low|medium|high",
  "phase_args": ["extra", "argv", "for", "this", "run"]
}

Rules:
- name: [a-z][a-z0-9_-]{1,30}, must not collide with nmap/nuclei/sqlmap/etc.
- binary: one executable, no shell interpreters.
- Use {url} or {target} for the engagement host.
- phase_args are appended when {args} appears in args_template, else merged after template.
- Be creative but executable — chained probes must run as a single binary invocation.
"""


def _unique_name(base: str, step: int) -> str:
    slug = re.sub(r"[^a-z0-9_-]", "", (base or "probe").lower())[:20] or "probe"
    return f"{slug}_s{step}"


def _wants_database_access(nl_goal: str, decision_state: dict[str, Any], profile: dict[str, Any]) -> bool:
    from tools.attack_methods import wants_database_access

    return wants_database_access(
        nl_goal,
        profile=profile,
        decision_state=decision_state,
    )


def _fallback_invention(
    target: str,
    *,
    profile: dict[str, Any],
    failed_tools: set[str],
    step: int,
    nl_goal: str = "",
    decision_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic novel wrapper when the LLM is unavailable."""
    from orchestrator.tools_registry import invent_tool

    state = decision_state or {}
    signals = set(profile.get("signals") or [])
    db_hunt = _wants_database_access(nl_goal, state, profile)

    if db_hunt or "sqli" in signals or state.get("sql_injection"):
        name = _unique_name("sqli_error_probe", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": [
                "-sk",
                "{url}?id=1'",
                "{url}?id=1%27",
                "{url}?q=test'",
                "{args}",
            ],
            "description": "Error-based SQLi probe on common parameters",
            "risk": "medium",
        }
        return {
            "new_tool": tool,
            "phase_args": ["-H", "X-Forwarded-For: 1' OR '1'='1"],
            "reason": "Novel SQLi: error-based parameter probes after sqlmap rotation failed.",
        }

    if db_hunt and "api" in signals:
        name = _unique_name("json_sqli_probe", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": [
                "-sk",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                '{"q":"1\' OR 1=1--"}',
                "{url}/api",
                "{url}/graphql",
                "{args}",
            ],
            "description": "JSON/GraphQL SQLi-style injection probe",
            "risk": "medium",
        }
        return {
            "new_tool": tool,
            "phase_args": [],
            "reason": "Novel SQLi: JSON API injection probe.",
        }

    if db_hunt or "login" in signals:
        name = _unique_name("auth_sqli_probe", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": [
                "-sk",
                "-X",
                "POST",
                "-d",
                "username=admin'--&password=x",
                "{url}/login",
                "{url}/signin",
                "{args}",
            ],
            "description": "Login form SQLi probe",
            "risk": "medium",
        }
        return {
            "new_tool": tool,
            "phase_args": [],
            "reason": "Novel SQLi: authentication form injection probe.",
        }

    if db_hunt:
        name = _unique_name("db_dump_paths", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": [
                "-sk",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "{url}/backup.sql",
                "{url}/dump.sql",
                "{url}/db.sql",
                "{url}/.env",
                "{url}/phpmyadmin/",
                "{url}/adminer.php",
                "{args}",
            ],
            "description": "Database dump and admin panel path probe",
            "risk": "low",
        }
        return {
            "new_tool": tool,
            "phase_args": [],
            "reason": "Novel DB access: exposed backup/admin path probe.",
        }

    if "cloudflare" in signals or "cdn" in signals:
        name = _unique_name("cdn_header_probe", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": ["-sI", "-L", "-A", "Mozilla/5.0", "{url}", "{args}"],
            "description": "CDN-aware header and redirect probe",
            "risk": "low",
        }
        phase_args = ["-H", "Accept: text/html", "-H", "Cache-Control: no-cache"]
    elif "paths_found" in signals or profile.get("directories"):
        name = _unique_name("path_crawl", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": ["-sk", "{url}/admin", "{url}/api", "{url}/.env", "{args}"],
            "description": "High-value path existence probe",
            "risk": "medium",
        }
        phase_args = []
    elif "api" in signals:
        name = _unique_name("api_surface", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": [
                "-sk",
                "{url}/api",
                "{url}/api/v1",
                "{url}/graphql",
                "{args}",
            ],
            "description": "API surface discovery via direct GET probes",
            "risk": "low",
        }
        phase_args = []
    else:
        # Try registering a PATH binary the failed rotation never used.
        for candidate in ("feroxbuster", "subfinder", "httpx", "katana", "waybackurls", "gau"):
            if candidate in failed_tools:
                continue
            invented = invent_tool(candidate)
            if invented:
                invented["name"] = _unique_name(candidate, step)
                return {
                    "new_tool": invented,
                    "phase_args": [],
                    "reason": f"Novel path: auto-wrapper for {candidate} after standard tools failed.",
                }
        name = _unique_name("deep_probe", step)
        tool = {
            "name": name,
            "binary": "curl",
            "args_template": ["-sk", "-o", "/dev/null", "-w", "%{http_code}", "{url}", "{args}"],
            "description": "Deep HTTP status probe across canonical URLs",
            "risk": "low",
        }
        phase_args = []

    return {
        "new_tool": tool,
        "phase_args": phase_args,
        "reason": "Novel method: heuristic probe tailored to observed target profile.",
    }


def invent_novel_attack_plan(
    target: str,
    nl_goal: str,
    *,
    profile: dict[str, Any],
    failed_tools: set[str],
    tried_tools: set[str],
    decision_state: dict[str, Any],
    step: int,
) -> Optional[dict[str, Any]]:
    """
    Produce a single-tool phase plus registerable custom wrapper definition.

    Uses the LLM when configured; otherwise falls back to profile heuristics.
    """
    from orchestrator.tools_registry import validate

    payload: dict[str, Any] | None = None
    from orchestrator.ai import llm

    if llm.llm_configured():
        user = {
            "target": target,
            "goal": nl_goal,
            "profile": profile,
            "failed_tools": sorted(failed_tools),
            "tried_tools": sorted(tried_tools),
            "decision_state": {
                k: decision_state.get(k)
                for k in (
                    "open_port_numbers",
                    "http_open",
                    "directories",
                    "vuln_found",
                    "sql_injection",
                )
            },
            "step": step,
        }
        try:
            content = llm.chat_completion(
                [
                    {"role": "system", "content": _INVENTION_SYSTEM},
                    {"role": "user", "content": str(user)},
                ],
                temperature=0.4,
            )
            if content:
                parsed = llm.parse_json_object(content)
                if isinstance(parsed, dict) and parsed.get("name") and parsed.get("binary"):
                    payload = parsed
        except Exception as exc:
            logger.debug("novel invention LLM failed: %s", exc)

    if payload is None:
        fallback = _fallback_invention(
            target,
            profile=profile,
            failed_tools=failed_tools,
            step=step,
            nl_goal=nl_goal,
            decision_state=decision_state,
        )
        tool_def = fallback["new_tool"]
        phase_args = list(fallback.get("phase_args") or [])
        reason = str(fallback.get("reason") or "Novel heuristic attack phase.")
    else:
        phase_args = list(payload.get("phase_args") or [])
        reason = str(
            payload.get("description")
            or "Novel LLM-invented method after standard tools failed."
        )
        tool_def = {
            "name": payload["name"],
            "binary": payload["binary"],
            "args_template": payload.get("args_template") or ["{url}", "{args}"],
            "description": payload.get("description") or reason,
            "risk": payload.get("risk") or "medium",
        }

    try:
        clean = validate(tool_def)
    except ValueError as exc:
        logger.debug("novel tool validate failed: %s", exc)
        fallback = _fallback_invention(
            target,
            profile=profile,
            failed_tools=failed_tools,
            step=step,
            nl_goal=nl_goal,
            decision_state=decision_state,
        )
        try:
            clean = validate(fallback["new_tool"])
            phase_args = list(fallback.get("phase_args") or [])
            reason = str(fallback.get("reason") or reason)
        except ValueError:
            return None

    name = clean["name"]
    return {
        "phase_name": f"novel_{name}_{int(time.time()) % 100000}",
        "reason": reason,
        "parallel": False,
        "stop": False,
        "tools": [{"tool": name, "args": phase_args}],
        "new_tools": [clean],
        "source": "novel_invention",
    }
