"""Dark web OSINT wrapper — authorized leak/onion intelligence only."""

from __future__ import annotations

from typing import Any

from tools.dark_web import (
    dark_web_enabled,
    parse_method_args,
    parse_osint_seeds_args,
    run_dark_web_method,
)


def scan(target: str, args=None) -> dict[str, Any]:
    if not dark_web_enabled():
        return {
            "tool": "darkweb",
            "target": target,
            "skipped": True,
            "error": "Dark web OSINT disabled (FIREBREAK_DARKWEB_ENABLED=false)",
        }
    method = parse_method_args(args)
    seeds = parse_osint_seeds_args(target, args)
    result = run_dark_web_method(method, target, seeds=seeds)
    result["tool"] = "darkweb"
    if result.get("findings") is None and result.get("productive"):
        findings = []
        for onion in result.get("onions") or []:
            findings.append({"type": "onion", "value": onion})
        for hit in result.get("hits") or []:
            for snip in hit.get("snippets") or []:
                findings.append({"type": "mention", "snippet": snip})
        if findings:
            result["findings"] = findings
    return result
