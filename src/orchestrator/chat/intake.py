"""Mission-intake agent: clarify + extract launch parameters (not kill-chain planner)."""

from __future__ import annotations

import re
from typing import Any, Optional

from orchestrator.ai.llm import chat_completion, parse_json_object
from orchestrator.ai.posture import normalize_posture

SOFT_FALLBACK = (
    "I couldn’t parse that — switch to Manual or retry."
)

INTAKE_SYSTEM = """You are Firebreak Mission Intake, a chat agent that helps authorized operators
define a mission. You do NOT run tools or plan kill-chain phases.

Return ONLY a single JSON object (no markdown fences):
{
  "reply": "short assistant message to the operator",
  "proposal": {
    "target": "hostname or URL or empty string",
    "posture": "balanced|aggressive|defensive",
    "nl_goal": "natural language goal or empty",
    "stealth": "off|low|high|null",
    "ready": false,
    "missing": ["target"]
  }
}

Rules:
- Scope: operator-AUTHORIZED engagements only. Refuse criminal/unauthorized targets in reply;
  set ready=false and explain.
- Ask one clarifying question at a time when information is missing.
- ready=true only when target is a concrete host/URL and the operator intent is clear.
- Prefer posture=balanced unless the operator asks otherwise.
- Keep reply concise (1-3 sentences).
"""

_HOST_RE = re.compile(
    r"(?i)\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?(?:/[^\s]*)?"
)


def _extract_target(text: str) -> str:
    m = _HOST_RE.search(text or "")
    if not m:
        return ""
    raw = m.group(0).strip().rstrip(".,)]")
    return raw


def _normalize_proposal(raw: Optional[dict[str, Any]], *, user_text: str) -> dict[str, Any]:
    raw = raw or {}
    target = str(raw.get("target") or "").strip() or _extract_target(user_text)
    posture = normalize_posture(str(raw.get("posture") or "balanced"))
    nl_goal = str(raw.get("nl_goal") or raw.get("goal") or "").strip()
    stealth = raw.get("stealth")
    if stealth in ("", "null", None):
        stealth = None
    elif stealth not in ("off", "low", "high"):
        stealth = "high"
    missing: list[str] = []
    if not target:
        missing.append("target")
    if missing:
        ready = False
    elif "ready" in raw:
        ready = bool(raw.get("ready"))
    else:
        ready = True
    return {
        "target": target,
        "posture": posture,
        "nl_goal": nl_goal or (f"Authorized assessment of {target}" if target else ""),
        "stealth": stealth,
        "ready": bool(ready and target),
        "missing": missing,
    }


def _heuristic(user_text: str, *, parse_failures: int) -> dict[str, Any]:
    proposal = _normalize_proposal({}, user_text=user_text)
    if proposal["ready"]:
        return {
            "reply": (
                f"I can launch a {proposal['posture']} mission against "
                f"{proposal['target']}. Confirm to proceed."
            ),
            "proposal": proposal,
        }
    if parse_failures >= 3:
        return {"reply": SOFT_FALLBACK, "proposal": proposal}
    return {
        "reply": "What target hostname or URL should this authorized mission use?",
        "proposal": proposal,
    }


def run_intake(
    messages: list[dict[str, str]],
    *,
    parse_failures: int = 0,
) -> dict[str, Any]:
    """Return `{reply, proposal}` for the latest user turn."""
    user_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_text = str(msg.get("content") or "")
            break

    llm_messages = [{"role": "system", "content": INTAKE_SYSTEM}]
    for msg in messages[-12:]:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        llm_messages.append({"role": role, "content": str(msg.get("content") or "")})

    content = chat_completion(llm_messages, temperature=0.2, timeout=60.0)
    if not content:
        return _heuristic(user_text, parse_failures=parse_failures)

    parsed = parse_json_object(content)
    if not parsed:
        # Keep asking toward a solution until soft fallback.
        if parse_failures >= 3:
            return _heuristic(user_text, parse_failures=parse_failures)
        base = _heuristic(user_text, parse_failures=0)
        if base["proposal"]["ready"]:
            return base
        return {
            "reply": (
                "I need a clearer target (hostname or URL) for this authorized mission. "
                "What should we assess?"
            ),
            "proposal": base["proposal"],
        }

    reply = str(parsed.get("reply") or "").strip()
    proposal = _normalize_proposal(
        parsed.get("proposal") if isinstance(parsed.get("proposal"), dict) else parsed,
        user_text=user_text,
    )
    if not reply:
        reply = (
            f"Ready to launch against {proposal['target']}."
            if proposal["ready"]
            else "What target should we use?"
        )
    return {"reply": reply, "proposal": proposal}
