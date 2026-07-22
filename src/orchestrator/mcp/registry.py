"""Tool registry metadata for MCP list_tools."""

from __future__ import annotations

from typing import Any

from orchestrator.tasks import _TASK_MAP
from tools.inventory import TOOL_CATALOG, catalog_by_name

HIGH_RISK = frozenset(
    entry["name"] for entry in TOOL_CATALOG if entry.get("risk") == "high"
)

_DESCRIPTIONS = {
    entry["name"]: entry["description"] for entry in TOOL_CATALOG
}


def list_tool_descriptors(category: str | None = None) -> list[dict[str, Any]]:
    catalog = catalog_by_name()
    tools = []
    for name in sorted(_TASK_MAP.keys()):
        meta = catalog.get(name, {})
        risk = meta.get("risk") or ("high" if name in HIGH_RISK else "low")
        if category == "high" and risk != "high":
            continue
        if category == "low" and risk != "low":
            continue
        if category and category not in {"high", "low"} and meta.get("category") != category:
            continue
        tools.append(
            {
                "name": name,
                "description": meta.get("description")
                or _DESCRIPTIONS.get(name, f"Firebreak tool: {name}"),
                "risk": risk,
                "category": meta.get("category"),
                "maturity": meta.get("maturity"),
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "use_proxy": {"type": "boolean"},
                        "proxy_protocol": {"type": "string"},
                        "confirm": {
                            "type": "boolean",
                            "description": "Required for high-risk tools when confirm mode is on",
                        },
                    },
                    "required": ["target"],
                },
            }
        )
    for custom in _custom_tools():
        risk = custom.get("risk") or "medium"
        if category == "high" and risk != "high":
            continue
        if category == "low" and risk != "low":
            continue
        if category and category not in {"high", "low"} and custom.get("category") != category:
            continue
        tools.append(
            {
                "name": custom["name"],
                "description": custom.get("description")
                or f"Custom tool: {custom['name']}",
                "risk": risk,
                "category": custom.get("category") or "custom",
                "maturity": "custom",
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "args": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["target"],
                },
            }
        )
    return tools


def _custom_tools() -> list[dict[str, Any]]:
    try:
        from orchestrator.tools_registry import list_tools

        return list_tools(include_disabled=False)
    except Exception:
        return []


def known_tools() -> set[str]:
    """Built-in wrappers plus enabled operator-approved custom tools."""
    names = set(_TASK_MAP.keys())
    names.update(t["name"] for t in _custom_tools() if t.get("name"))
    return names
