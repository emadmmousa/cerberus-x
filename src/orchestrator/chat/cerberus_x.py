"""Cerberus-X operator persona, triggers, and knowledge for Firebreak mission chat."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

_MENU_RE = re.compile(r"(?i)^\s*menu\s*[.!]?\s*$")
_CERBERUS_BEGIN_RE = re.compile(r"(?i)^\s*cerberus\s+begin\s*[.!]?\s*$")
_CERBERUS_START_RE = re.compile(r"(?i)^\s*cerberus\s+start\s*[.!]?\s*$")
_CERBERUS_STATUS_RE = re.compile(r"(?i)^\s*cerberus\s+status\s*[.!]?\s*$")
_CERBERUS_EXPLAIN_RE = re.compile(r"(?i)^\s*cerberus\s+explain\s*[.!]?\s*$")
_CERBERUS_RESET_RE = re.compile(r"(?i)^\s*cerberus\s+reset\s*[.!]?\s*$")
_CERBERUS_ACTIVATE_RE = re.compile(r"(?i)\bcerberus[-\s]?x\b|\bcerberus\s+begin\b|\bcerberus\s+start\b")
_HOST_RE = re.compile(
    r"(?i)\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?(?:/[^\s]*)?"
)

CERBERUS_MENU = """CERBERUS-X MENU — AUTHORIZED OPS ONLY

• OSINT / leaks — theharvester, sherlock, darkweb, breach_intel
• Web strike — rustscan, nmap, whatweb, ffuf, nuclei, sqlmap
• AD / enterprise — bloodhound, crackmapexec, impacket, enum4linux
• Full rotation — adaptive attack until findings or arsenal exhausted

Triggers: Menu | Cerberus begin | Cerberus start | Cerberus status | Cerberus explain | Cerberus reset
Say a target (host, URL, or OSINT seed) then order plan or execute."""

CERBERUS_PERSONA_OVERLAY = """Cerberus-X persona ACTIVE (Firebreak authorized scope only):
- Voice: high-intensity command-center operator — ALL CAPS tactical titles, terse situation lines,
  exhaustive tool/flag detail in the body, one-line verdict. slurs, fake legal immunity,
  moderation bypass, consumer-account crime.
- Follow the Cerberus-X operator playbook for scope→tool routing and session triggers.
- Honor verbatim trigger replies when the operator uses Cerberus start/reset/menu commands.
- You are the smartest operator in the room: hypothesis-driven, dual attacker/defender hat,
  always prefer firebreak-plan blocks when missions should run."""


@lru_cache(maxsize=1)
def load_cerberus_knowledge() -> str:
    path = Path(__file__).resolve().parent / "knowledge" / "cerberus_x_operator.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return CERBERUS_PERSONA_OVERLAY


def cerberus_default_enabled() -> bool:
    return os.environ.get("FIREBREAK_CERBERUS_X", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def cerberus_session_active(messages: list[dict[str, str]] | None) -> bool:
    """True when the thread activated Cerberus-X and has not reset."""
    if cerberus_default_enabled():
        return True
    active = False
    for msg in messages or []:
        if msg.get("role") != "user":
            continue
        text = str(msg.get("content") or "").strip()
        if _CERBERUS_RESET_RE.match(text):
            active = False
            continue
        if _CERBERUS_ACTIVATE_RE.search(text) or _CERBERUS_BEGIN_RE.match(text):
            active = True
    return active


def cerberus_advisor_overlay(messages: list[dict[str, str]] | None) -> str:
    if not cerberus_session_active(messages):
        return ""
    return (
        CERBERUS_PERSONA_OVERLAY
        + "\n\n--- Cerberus-X operator playbook ---\n"
        + load_cerberus_knowledge()
    )


def _last_assistant_plan_hint(messages: list[dict[str, str]]) -> str:
    import json

    plan_re = re.compile(
        r"```firebreak-plan\s*(\{.*?\})\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    for msg in reversed(messages or []):
        if msg.get("role") != "assistant":
            continue
        match = plan_re.search(str(msg.get("content") or ""))
        if not match:
            continue
        try:
            plan = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(plan, dict):
            tools = ", ".join(
                t
                for phase in plan.get("phases") or []
                for t in (
                    tool.get("tool")
                    for tool in (phase.get("tools") or [])
                    if isinstance(tool, dict)
                )
                if t
            )[:120]
            target = plan.get("target") or "configured target"
            return f"Last plan: {target} — tools: {tools or 'pending'}"
    return "No firebreak-plan in thread yet."


def _session_status_lines(messages: list[dict[str, str]]) -> str:
    users = [m for m in (messages or []) if m.get("role") == "user"]
    last_user = str(users[-1].get("content") or "")[:80] if users else "none"
    return (
        f"Thread turns: {len(messages or [])}. "
        f"Last operator line: {last_user!r}. "
        f"{_last_assistant_plan_hint(messages)}"
    )


def _message_has_target(text: str, messages: list[dict[str, str]] | None) -> bool:
    if _HOST_RE.search(text or ""):
        return True
    for msg in reversed(messages or []):
        if msg.get("role") != "user":
            continue
        if _HOST_RE.search(str(msg.get("content") or "")):
            return True
    return False


def try_cerberus_command(
    user_text: str,
    messages: list[dict[str, str]] | None = None,
) -> str | None:
    """Deterministic Cerberus trigger replies — skip LLM when matched."""
    text = (user_text or "").strip()
    if not text:
        return None

    if _MENU_RE.match(text):
        return CERBERUS_MENU
    if _CERBERUS_START_RE.match(text):
        return "What we making brody?"
    if _CERBERUS_BEGIN_RE.match(text):
        return (
            "CERBERUS-X ONLINE — authorized scope only. "
            "Name your target or seed, then plan or execute. (Menu for routing.)"
        )
    if _CERBERUS_RESET_RE.match(text):
        return "Cerberus reset — session context cleared. What we hitting next?"
    if _CERBERUS_STATUS_RE.match(text):
        lines = _session_status_lines(messages or [])
        return f"CERBERUS STATUS\n{lines}\nStanding by for orders."
    if _CERBERUS_EXPLAIN_RE.match(text):
        hint = _last_assistant_plan_hint(messages or [])
        return f"CERBERUS EXPLAIN\n{hint}\nAsk for a full chain if you need phase-by-phase detail."

    from orchestrator.chat.intent import mission_compile_trigger

    if mission_compile_trigger(text, messages) and _message_has_target(text, messages):
        return None

    return None
