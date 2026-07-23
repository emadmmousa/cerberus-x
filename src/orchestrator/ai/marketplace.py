"""Scaffold marketplace catalog (Firebreak Wave 5).

Community can list the catalog. Registering custom scaffolds is a Pro packaging
hook — it does not gate core scanning.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from orchestrator.ai.scaffold_catalog import catalog_categories, cyber_scaffold_catalog
from security.edition import feature_flags, is_pro

MARKET_KEY = "firebreak:scaffold:marketplace"


def builtin_catalog() -> list[dict[str, Any]]:
    """Static catalog of known OpenAI-compatible scaffold recipes."""
    return cyber_scaffold_catalog()


def _redis():
    try:
        from utils.redis_utils import get_redis

        return get_redis()
    except Exception:
        return None


def list_registered() -> list[dict[str, Any]]:
    r = _redis()
    if r is None:
        return []
    try:
        raw = r.get(MARKET_KEY)
        if not raw:
            return []
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def register_scaffold(entry: dict[str, Any]) -> dict[str, Any]:
    """Register a custom scaffold recipe (Pro packaging)."""
    if not feature_flags().get("scaffold_marketplace"):
        raise PermissionError("scaffold marketplace requires FIREBREAK_EDITION=pro")
    sid = str(entry.get("id") or "").strip()
    model = str(entry.get("model") or "").strip()
    base = str(entry.get("base_url") or entry.get("base_url_hint") or "").strip()
    if not sid or not model:
        raise ValueError("id and model are required")
    if not base:
        raise ValueError("base_url is required to wire a live scaffold")
    try:
        cost = float(entry.get("cost_per_1k") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    row = {
        "id": sid[:64],
        "label": str(entry.get("label") or sid)[:128],
        "kind": str(entry.get("kind") or "openai_compatible"),
        "model": model[:128],
        "base_url": base[:256],
        "base_url_hint": base[:256],
        "api_key_env": str(entry.get("api_key_env") or "FIREBREAK_LLM_API_KEY")[:64],
        "tasks": list(entry.get("tasks") or ["plan"]),
        "license": str(entry.get("license") or "unknown")[:64],
        "cost_per_1k": max(0.0, cost),
        "enabled": bool(entry.get("enabled", True)),
        "source": "registered",
        "registered_at": time.time(),
    }
    if entry.get("category"):
        row["category"] = str(entry.get("category"))[:128]
    if entry.get("notes"):
        row["notes"] = str(entry.get("notes"))[:512]
    rows = [r for r in list_registered() if r.get("id") != row["id"]]
    rows.append(row)
    r = _redis()
    if r is not None:
        try:
            r.set(MARKET_KEY, json.dumps(rows), ex=86400 * 30)
        except Exception:
            pass
    return row


def unregister_scaffold(scaffold_id: str) -> bool:
    """Remove a registered scaffold (Pro). Builtin catalog entries cannot be removed."""
    if not feature_flags().get("scaffold_marketplace"):
        raise PermissionError("scaffold marketplace requires FIREBREAK_EDITION=pro")
    sid = str(scaffold_id or "").strip()
    if not sid:
        raise ValueError("id is required")
    rows = list_registered()
    kept = [r for r in rows if r.get("id") != sid]
    if len(kept) == len(rows):
        return False
    r = _redis()
    if r is not None:
        try:
            r.set(MARKET_KEY, json.dumps(kept), ex=86400 * 30)
        except Exception:
            pass
    return True


def marketplace_status() -> dict[str, Any]:
    catalog = builtin_catalog()
    registered = list_registered()
    return {
        "edition": "pro" if is_pro() else "community",
        "can_register": bool(feature_flags().get("scaffold_marketplace")),
        "catalog": catalog,
        "categories": catalog_categories(catalog),
        "registered": registered,
        "count": len(catalog) + len(registered),
        "notes": (
            "Catalog is readable in community; registering custom scaffolds "
            "is a Pro packaging hook and does not paywall scanning."
        ),
    }
