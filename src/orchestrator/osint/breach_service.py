"""Orchestrate breach lookups across DeHashed and LeakCheck for OSINT seeds."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from orchestrator.osint.breach_branding import sanitize_breach_payload
from orchestrator.osint.breach_providers import (
    breach_intel_enabled,
    build_dehashed_query,
    dehashed_search,
    leakcheck_lookup,
    leakcheck_query_type,
    provider_status,
    redact_breach_record,
)
from orchestrator.osint.seeds import normalize_osint_seeds, primary_mission_target


def _seed_match_tokens(seed: dict[str, str]) -> list[str]:
    kind = str(seed.get("kind") or "")
    value = str(seed.get("value") or "").strip()
    display = str(seed.get("display") or value).strip()
    tokens: list[str] = []
    for token in (display, value):
        lowered = token.lower()
        if len(lowered) >= 3:
            tokens.append(lowered)
    if kind == "email" and "@" in value:
        local = value.split("@", 1)[0].lower()
        if len(local) >= 2:
            tokens.append(local)
        tokens.append(value.lower())
    if kind == "domain":
        tokens.append(f"@{value.lower()}")
    if kind == "username":
        tokens.append(value.lstrip("@").lower())
    if kind == "social_url":
        handle = _social_handle(value)
        if handle and len(handle) >= 2:
            tokens.append(handle.lower())
    return list(dict.fromkeys(tokens))


def _record_matches_seed(entry: dict[str, Any], seed: dict[str, str]) -> bool:
    if not isinstance(entry, dict):
        return False
    tokens = _seed_match_tokens(seed)
    if not tokens:
        return False
    blob = json.dumps(entry, default=str).lower()
    return any(token in blob for token in tokens)


def _filter_provider_entries(
    entries: list[Any] | None,
    seed: dict[str, str],
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for entry in entries or []:
        if isinstance(entry, dict) and _record_matches_seed(entry, seed):
            kept.append(entry)
    return kept


def _social_handle(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url.lstrip('/')}")
    parts = [p for p in (parsed.path or "").split("/") if p]
    if parts:
        return parts[-1].lstrip("@")
    return (parsed.hostname or "").split(".")[0]


def seeds_from_target_and_args(target: str, args: list[str] | None) -> list[dict[str, str]]:
    seeds: list[dict[str, str]] = []
    argv = list(args or [])
    for idx, token in enumerate(argv):
        if token in {"--seeds", "--osint-seeds"} and idx + 1 < len(argv):
            try:
                raw = json.loads(argv[idx + 1])
                if isinstance(raw, list):
                    seeds.extend(normalize_osint_seeds(raw))
            except json.JSONDecodeError:
                pass
    if not seeds and (target or "").strip():
        seeds = normalize_osint_seeds([{"value": target}])
    return seeds


def lookup_seed(seed: dict[str, str], *, per_provider_limit: int = 25) -> dict[str, Any]:
    kind = str(seed.get("kind") or "")
    value = str(seed.get("value") or "")
    display = str(seed.get("display") or value)
    query_value = value
    if kind == "social_url":
        handle = _social_handle(value)
        if handle:
            query_value = handle

    dehashed_query = build_dehashed_query(kind, value)
    if kind == "social_url" and query_value and query_value != value:
        dehashed_query = build_dehashed_query("username", query_value)
    dehashed = dehashed_search(dehashed_query, size=per_provider_limit)
    leakcheck = leakcheck_lookup(
        query_value,
        query_type=leakcheck_query_type(kind),
        limit=per_provider_limit,
    )
    seed_row = {"kind": kind, "value": value, "display": display}
    dh_entries = _filter_provider_entries(dehashed.get("entries"), seed_row)
    lc_entries = _filter_provider_entries(leakcheck.get("entries"), seed_row)
    dehashed = {**dehashed, "entries": dh_entries, "total": len(dh_entries)}
    leakcheck = {**leakcheck, "entries": lc_entries, "found": len(lc_entries)}
    total_hits = len(dh_entries) + len(lc_entries)
    return {
        "seed": {"kind": kind, "value": value, "display": display},
        "dehashed": dehashed,
        "leakcheck": leakcheck,
        "total_hits": total_hits,
        "productive": bool(dehashed.get("productive") or leakcheck.get("productive")),
    }


def lookup_seeds(seeds: list[dict[str, str]] | None, *, per_provider_limit: int = 25) -> dict[str, Any]:
    normalized = normalize_osint_seeds(seeds)
    status = provider_status()
    if not breach_intel_enabled():
        return sanitize_breach_payload(
            {
                "skipped": True,
                "error": "Exposure intel disabled (FIREBREAK_BREACH_INTEL_ENABLED=false)",
                "providers": status,
                "seeds": normalized,
            }
        )
    if not status.get("ready"):
        return sanitize_breach_payload(
            {
                "skipped": True,
                "error": "No exposure intel providers configured (set Breach Vault and/or Leak Radar API keys)",
                "providers": status,
                "seeds": normalized,
            }
        )

    rows = [lookup_seed(seed, per_provider_limit=per_provider_limit) for seed in normalized]
    databases: set[str] = set()
    sources: set[str] = set()
    for row in rows:
        dh = row.get("dehashed") or {}
        lc = row.get("leakcheck") or {}
        databases.update(dh.get("databases") or [])
        sources.update(lc.get("sources") or [])

    return sanitize_breach_payload(
        {
            "providers": status,
            "seeds": normalized,
            "results": rows,
            "summary": {
                "seed_count": len(normalized),
                "seeds_with_hits": sum(1 for row in rows if row.get("productive")),
                "total_hits": sum(int(row.get("total_hits") or 0) for row in rows),
                "dehashed_databases": sorted(databases)[:30],
                "leakcheck_sources": sorted(sources)[:30],
            },
            "productive": any(row.get("productive") for row in rows),
        }
    )


def lookup_target(target: str, args: list[str] | None = None, *, per_provider_limit: int = 25) -> dict[str, Any]:
    seeds = seeds_from_target_and_args(target, args)
    if not seeds:
        return sanitize_breach_payload(
            {
                "target": target,
                "error": "no OSINT seeds to query",
                "providers": provider_status(),
                "productive": False,
            }
        )
    payload = lookup_seeds(seeds, per_provider_limit=per_provider_limit)
    payload["target"] = target or primary_mission_target(seeds)
    findings = []
    for row in payload.get("results") or []:
        seed = row.get("seed") or {}
        label = seed.get("display") or seed.get("value")
        dh_total = len((row.get("dehashed") or {}).get("entries") or [])
        lc_found = len((row.get("leakcheck") or {}).get("entries") or [])
        if dh_total or lc_found:
            findings.append(
                {
                    "type": "breach_exposure",
                    "seed": label,
                    "dehashed_hits": dh_total,
                    "leakcheck_hits": lc_found,
                }
            )
        for entry in (row.get("dehashed") or {}).get("entries") or []:
            if isinstance(entry, dict):
                findings.append({"type": "dehashed_record", "seed": label, **redact_breach_record(entry)})
        for entry in (row.get("leakcheck") or {}).get("entries") or []:
            if isinstance(entry, dict):
                src = entry.get("source")
                name = src.get("name") if isinstance(src, dict) else src
                findings.append(
                    {
                        "type": "leakcheck_record",
                        "seed": label,
                        "source": name,
                        "fields": entry.get("fields"),
                        **{k: v for k, v in entry.items() if k not in {"source", "fields", "password"}},
                    }
                )
    if findings:
        payload["findings"] = findings[:100]
    return sanitize_breach_payload(payload)
