"""Breach intel wrapper — DeHashed + LeakCheck for authorized OSINT seeds."""

from __future__ import annotations

from typing import Any

from orchestrator.osint.breach_providers import breach_intel_enabled
from tools.breach_intel import scan


def run(target: str, args=None) -> dict[str, Any]:
    if not breach_intel_enabled():
        return {
            "tool": "breach_intel",
            "target": target,
            "skipped": True,
            "error": "Breach intel disabled (FIREBREAK_BREACH_INTEL_ENABLED=false)",
        }
    result = scan(target, list(args) if args else None)
    result["tool"] = "breach_intel"
    return result
