"""Scaffold registry with optional Redis persistence (Firebreak W1)."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from orchestrator.ai.scaffold_client import (
    build_extra_scaffold,
    build_fallback_scaffold,
    build_from_registry_row,
    build_primary_scaffold,
)

REGISTRY_KEY = "firebreak:scaffolds"


def _redis():
    try:
        from utils.redis_utils import get_redis

        return get_redis()
    except Exception:
        return None


def _row_from_client(client) -> dict[str, Any]:
    return {
        "id": client.spec.id,
        "kind": "openai_compatible",
        "model": client.spec.model,
        "base_url": client.spec.base_url,
        "tasks": list(client.spec.tasks),
        "enabled": True,
        "cost_per_1k": client.spec.cost_per_1k,
        "source": "env",
        "registered_at": time.time(),
    }


def default_scaffolds() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for builder in (build_primary_scaffold, build_fallback_scaffold, build_extra_scaffold):
        client = builder()
        if not client or client.spec.id in seen:
            continue
        seen.add(client.spec.id)
        rows.append(_row_from_client(client))

    # Marketplace registrations (Pro) — live when base_url + model present.
    try:
        from orchestrator.ai.marketplace import list_registered

        for entry in list_registered():
            sid = str(entry.get("id") or "")
            if not sid or sid in seen:
                continue
            if not (entry.get("base_url") or entry.get("base_url_hint")):
                continue
            if not entry.get("model"):
                continue
            row = {
                "id": sid,
                "kind": entry.get("kind") or "openai_compatible",
                "model": entry.get("model"),
                "base_url": entry.get("base_url") or entry.get("base_url_hint"),
                "api_key_env": entry.get("api_key_env") or "FIREBREAK_LLM_API_KEY",
                "tasks": list(entry.get("tasks") or ["plan_phase"]),
                "enabled": entry.get("enabled", True),
                "cost_per_1k": float(entry.get("cost_per_1k") or 0.0),
                "source": "marketplace",
                "registered_at": entry.get("registered_at") or time.time(),
            }
            # Validate client can be built
            if build_from_registry_row(row):
                seen.add(sid)
                rows.append(row)
    except Exception:
        pass
    return rows


def publish_registry(rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = rows if rows is not None else default_scaffolds()
    r = _redis()
    if r is not None:
        try:
            r.set(REGISTRY_KEY, json.dumps(rows), ex=3600)
        except Exception:
            pass
    return rows


def list_enabled() -> list[dict[str, Any]]:
    return [s for s in publish_registry() if s.get("enabled")]


def build_enabled_clients() -> list:
    """Instantiate OpenAI-compatible clients for every enabled registry row."""
    clients = []
    for row in list_enabled():
        client = build_from_registry_row(row)
        if client:
            clients.append(client)
    return clients


def multi_scaffold_enabled() -> bool:
    raw = (os.environ.get("FIREBREAK_MULTI_SCAFFOLD") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _latency_key(scaffold_id: str) -> str:
    return f"firebreak:scaffold:latency:{scaffold_id}"


def record_latency(scaffold_id: str, latency_ms: float, *, alpha: float = 0.2) -> float:
    """Update exponential moving average of scaffold latency in Redis."""
    r = _redis()
    ema = float(latency_ms)
    if r is not None:
        try:
            prev = r.get(_latency_key(scaffold_id))
            if prev is not None:
                ema = alpha * float(latency_ms) + (1.0 - alpha) * float(prev)
            if hasattr(r, "setex"):
                r.setex(_latency_key(scaffold_id), 86400, str(ema))
            else:
                r.set(_latency_key(scaffold_id), str(ema))
        except Exception:
            pass
    return ema


def latency_ema(scaffold_id: str) -> float | None:
    r = _redis()
    if r is None:
        return None
    try:
        raw = r.get(_latency_key(scaffold_id))
        return float(raw) if raw is not None else None
    except Exception:
        return None


def health_all() -> list[dict[str, Any]]:
    out = []
    for row in list_enabled():
        client = build_from_registry_row(row)
        if not client:
            out.append({**row, "ok": False, "error": "missing base_url or model"})
            continue
        health = client.health()
        if health.get("latency_ms") is not None:
            ema = record_latency(row["id"], float(health["latency_ms"]))
            health["latency_ema_ms"] = int(ema)
        else:
            prev = latency_ema(row["id"])
            if prev is not None:
                health["latency_ema_ms"] = int(prev)
        out.append({**row, **health})
    return out
