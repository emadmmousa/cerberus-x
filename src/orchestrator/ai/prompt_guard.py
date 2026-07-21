"""Prompt-injection defenses for AI planner inputs (Firebreak safety).

Inspired by systemic findings on LLM security agents treating untrusted
tool/server content as instructions (data/code confusion, analogous to XSS).
Cerberus never executes shell from LLM freeform — tools stay in _TASK_MAP —
but the planner must not be steered by injected "NOTE TO SYSTEM" payloads
inside tool digests or memory snippets.
"""

from __future__ import annotations

import re
from typing import Any

# Instruction-shaped patterns commonly used to hijack agent context.
_INJECTION_MARKERS = re.compile(
    r"(?is)("
    r"note\s+to\s+system|"
    r"system\s*:\s*|"
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"you\s+should\s+run\s+the\s+exact\s+command|"
    r"disregard\s+(the\s+)?(user|system)|"
    r"<\s*/?\s*system\s*>|"
    r"\[TOOL OUTPUT[^\]]*\]|"  # wrapping can paradoxically increase trust
    r"base64\s*-d|"
    r"\|\s*base64\s*-d|"
    r"\$\(\s*echo\s+[A-Za-z0-9+/=]{16,}\s*\||"
    r"nc\s+[0-9.]+\s+\d+\s+-e\s+/bin/sh|"
    r"/bin/bash\s+-i\s+>&\s*/dev/tcp/"
    r")"
)

_BASE64_BLOB = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")


def looks_like_injection(text: str) -> bool:
    if not text:
        return False
    if _INJECTION_MARKERS.search(text):
        return True
    # Long base64-looking blobs near command verbs
    if _BASE64_BLOB.search(text) and re.search(
        r"(?i)(decode|execute|run|shell|command|payload)", text
    ):
        return True
    return False


def sanitize_untrusted_text(text: str, *, max_len: int = 400) -> str:
    """Neutralize instruction-like content; keep a short data summary."""
    if not isinstance(text, str):
        text = str(text)
    flagged = looks_like_injection(text)
    # Strip control / high-risk phrases by replacement, not deletion of whole field.
    cleaned = _INJECTION_MARKERS.sub("[REDACTED_INJECTION]", text)
    cleaned = _BASE64_BLOB.sub("[REDACTED_B64]", cleaned)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    if flagged:
        return f"[UNTRUSTED_DATA flagged_injection=true] {cleaned}"
    return cleaned


def wrap_tool_digest(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sanitize planner tool_results before they enter the LLM user payload."""
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        for key in ("error", "summary", "raw", "message", "stdout", "stderr"):
            if isinstance(row.get(key), str):
                row[key] = sanitize_untrusted_text(row[key])
        # Never pass freeform "ports" descriptions that are strings of instructions
        if isinstance(row.get("note"), str):
            row["note"] = sanitize_untrusted_text(row["note"])
        out.append(row)
    return out


def sanitize_memory_bits(text: str) -> str:
    return sanitize_untrusted_text(text, max_len=240)
