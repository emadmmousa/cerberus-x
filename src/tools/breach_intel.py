"""Breach intelligence tool — DeHashed + LeakCheck lookups for authorized OSINT."""

from __future__ import annotations

import json
from typing import Any

from orchestrator.osint.breach_service import lookup_target


def parse_limit_args(args: list[str] | None) -> int:
    argv = list(args or [])
    for idx, token in enumerate(argv):
        if token in {"--limit", "-l"} and idx + 1 < len(argv):
            try:
                return max(1, min(100, int(argv[idx + 1])))
            except ValueError:
                return 25
        if token.startswith("--limit="):
            try:
                return max(1, min(100, int(token.split("=", 1)[1])))
            except ValueError:
                return 25
    return 25


def with_osint_seeds_args(args: list[str] | None, seeds: list[dict[str, str]] | None) -> list[str]:
    argv = list(args or [])
    if not seeds:
        return argv
    if any(token in argv for token in ("--seeds", "--osint-seeds")):
        return argv
    return [*argv, "--seeds", json.dumps(seeds)]


_OSINT_SEED_TOOLS = frozenset(
    {
        "theharvester",
        "subfinder",
        "gau",
        "sherlock",
        "katana",
        "httpx",
        "whatweb",
        "darkweb",
        "breach_intel",
    }
)


def inject_osint_seeds_into_tools(
    tools: list[dict[str, Any]] | None,
    seeds: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    if not seeds:
        return list(tools or [])
    out: list[dict[str, Any]] = []
    for entry in tools or []:
        if not isinstance(entry, dict):
            continue
        row = dict(entry)
        tool_name = str(row.get("tool") or "").strip().lower()
        if tool_name in _OSINT_SEED_TOOLS:
            row["args"] = with_osint_seeds_args(row.get("args"), seeds)
        out.append(row)
    return out


def scan(target: str, args: list[str] | None = None) -> dict[str, Any]:
    limit = parse_limit_args(args)
    result = lookup_target(target, args, per_provider_limit=limit)
    result["tool"] = "breach_intel"
    return result


def list_breach_methods() -> dict[str, list[str]]:
    return {
        "providers": ["breach_vault", "leak_radar"],
        "modes": ["lookup", "full"],
        "seed_kinds": ["email", "username", "mobile", "domain", "full_name", "social_url"],
    }
