"""AI safety helpers — risk classes and confirm gates."""

from __future__ import annotations

import os

from orchestrator.mcp.registry import HIGH_RISK


def confirm_required_globally() -> bool:
    return os.environ.get("CERBERUS_AI_REQUIRE_CONFIRM", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def is_high_risk(tool: str) -> bool:
    return tool in HIGH_RISK


def require_confirm_for_tool(tool: str) -> bool:
    """True when this tool call must include confirm=true."""
    return confirm_required_globally() and is_high_risk(tool)
