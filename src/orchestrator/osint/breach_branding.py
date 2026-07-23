"""Commercial product names for breach-intel integrations (operator-facing only)."""

from __future__ import annotations

import re
from typing import Any

BREACH_VAULT_PRODUCT = "Breach Vault"
LEAK_RADAR_PRODUCT = "Leak Radar"

_INTERNAL_PROVIDER_KEYS = frozenset({"dehashed", "leakcheck"})
_PROVIDER_PRODUCT: dict[str, str] = {
    "dehashed": BREACH_VAULT_PRODUCT,
    "leakcheck": LEAK_RADAR_PRODUCT,
}
_PROVIDER_API_KEY: dict[str, str] = {
    "dehashed": "breach_vault",
    "leakcheck": "leak_radar",
}

_ENV_NAME_RE = re.compile(
    r"(?i)\b(DEHASHED|LEAKCHECK|FIREBREAK_DEHASHED|FIREBREAK_LEAKCHECK)(?:_API_KEY|_APIKEY)?\b"
)


def provider_product_name(provider: str | None) -> str:
    key = str(provider or "").strip().lower()
    return _PROVIDER_PRODUCT.get(key, BREACH_VAULT_PRODUCT if key else "")


def sanitize_operator_message(text: str | None) -> str:
    """Replace internal provider/env names in operator-visible strings."""
    if not text:
        return ""
    out = str(text)
    out = _ENV_NAME_RE.sub(lambda m: _env_replacement(m.group(0)), out)
    out = re.sub(r"(?i)\bdehashed\b", BREACH_VAULT_PRODUCT, out)
    out = re.sub(r"(?i)\bleakcheck\b", LEAK_RADAR_PRODUCT, out)
    return out


def _env_replacement(token: str) -> str:
    upper = token.upper()
    if "LEAKCHECK" in upper:
        return LEAK_RADAR_PRODUCT
    return BREACH_VAULT_PRODUCT


def sanitize_provider_payload(record: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    out = dict(record)
    provider = str(out.pop("provider", "") or "").strip().lower()
    if provider in _PROVIDER_PRODUCT:
        out["product"] = _PROVIDER_PRODUCT[provider]
    if "error" in out and out["error"]:
        out["error"] = sanitize_operator_message(str(out["error"]))
    if "query" in out and out["query"]:
        out["query"] = str(out["query"])
    return out


def sanitize_provider_status(status: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(status or {})
    out: dict[str, Any] = {
        "enabled": raw.get("enabled"),
        "ready": raw.get("ready"),
    }
    for internal, external in _PROVIDER_API_KEY.items():
        block = raw.get(internal)
        if isinstance(block, dict):
            row = dict(block)
            row["product"] = _PROVIDER_PRODUCT[internal]
            out[external] = row
    return out


def sanitize_seed_lookup_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    out: dict[str, Any] = {
        "seed": row.get("seed"),
        "total_hits": row.get("total_hits"),
        "productive": row.get("productive"),
    }
    for internal, external in _PROVIDER_API_KEY.items():
        block = row.get(internal)
        if isinstance(block, dict):
            out[external] = sanitize_provider_payload(block)
    return out


def sanitize_breach_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    out = dict(summary)
    if "dehashed_databases" in out:
        out["breach_vault_databases"] = out.pop("dehashed_databases")
    if "leakcheck_sources" in out:
        out["leak_radar_sources"] = out.pop("leakcheck_sources")
    return out


def sanitize_breach_findings(findings: list[Any] | None) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in findings or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        ftype = str(row.get("type") or "")
        if ftype == "dehashed_record":
            row["type"] = "breach_vault_record"
        elif ftype == "leakcheck_record":
            row["type"] = "leak_radar_record"
        if "dehashed_hits" in row:
            row["breach_vault_hits"] = row.pop("dehashed_hits")
        if "leakcheck_hits" in row:
            row["leak_radar_hits"] = row.pop("leakcheck_hits")
        cleaned.append(row)
    return cleaned


def sanitize_breach_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Strip internal provider identifiers from breach-intel tool/API payloads."""
    if not isinstance(payload, dict):
        return {}
    out = dict(payload)
    if "error" in out and out["error"]:
        out["error"] = sanitize_operator_message(str(out["error"]))
    if "providers" in out:
        out["providers"] = sanitize_provider_status(out.get("providers"))
    if "summary" in out:
        out["summary"] = sanitize_breach_summary(out.get("summary"))
    if "results" in out:
        out["results"] = [
            sanitize_seed_lookup_row(row)
            for row in (out.get("results") or [])
            if isinstance(row, dict)
        ]
    if "findings" in out:
        out["findings"] = sanitize_breach_findings(out.get("findings"))
    return out
