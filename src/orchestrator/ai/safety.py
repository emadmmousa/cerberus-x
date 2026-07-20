"""AI safety helpers — risk classes and confirm gates."""

from __future__ import annotations

import os


def _high_risk() -> set[str]:
    # Lazy import avoids circular import: mcp.actions → safety → mcp.registry.
    from orchestrator.mcp.registry import HIGH_RISK

    return HIGH_RISK


def confirm_required_globally() -> bool:
    # Default OFF — unrestricted orchestration unless explicitly re-enabled.
    return os.environ.get("CERBERUS_AI_REQUIRE_CONFIRM", "false").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def is_high_risk(tool: str) -> bool:
    return tool in _high_risk()


def require_confirm_for_tool(tool: str) -> bool:
    """True when this tool call must include confirm=true."""
    return confirm_required_globally() and is_high_risk(tool)
