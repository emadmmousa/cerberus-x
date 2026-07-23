"""Normalize wrapper payloads for UI display (flags missing on legacy rows)."""

from __future__ import annotations

from typing import Any


def enrich_tool_result(tool: str | None, payload: Any) -> Any:
    """Add derived status flags when older runs omitted them."""
    if not isinstance(payload, dict):
        return payload

    name = str(tool or payload.get("tool") or "").strip().lower()
    if not name:
        return payload

    out = dict(payload)
    if name == "sqlmap":
        from tools.wrappers.sqlmap import _analyze_sqlmap_output

        raw = str(out.get("raw_output") or out.get("error") or "")
        vulnerable = bool(out.get("vulnerable"))
        for key, value in _analyze_sqlmap_output(raw, vulnerable=vulnerable).items():
            if key not in out or out.get(key) in (None, False, ""):
                out[key] = value
    elif name == "whatweb":
        from tools.wrappers import whatweb

        raw = str(out.get("raw_output") or "")
        status = str(out.get("http_status") or "")
        if not out.get("waf_blocked"):
            waf = whatweb._detect_waf_challenge(raw, status or None)
            if waf.get("waf_blocked"):
                out["waf_blocked"] = True
                out["partial"] = True
                out.setdefault(
                    "note",
                    f"{waf.get('waf_vendor') or 'WAF'} challenge page detected "
                    f"({status or 'blocked'}) — app fingerprint limited.",
                )
    elif name == "metasploit":
        err = str(out.get("error") or "")
        if out.get("code") == "rpc_error" and "invalid module" in err.lower():
            out["code"] = "invalid_module"
    return out


def enrich_result_row(row: dict) -> dict:
    if not isinstance(row, dict):
        return row
    tool = row.get("tool")
    result = row.get("result")
    if isinstance(result, dict):
        return {**row, "result": enrich_tool_result(tool, result)}
    return row


def enrich_result_rows(rows: list) -> list:
    return [enrich_result_row(row) for row in rows]
