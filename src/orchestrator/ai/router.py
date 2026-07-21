"""Multi-scaffold router for planner completions (Firebreak W1)."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from orchestrator.ai import llm
from orchestrator.ai.scaffold_client import build_primary_scaffold
from orchestrator.ai.scaffolds import (
    build_enabled_clients,
    latency_ema,
    multi_scaffold_enabled,
)

logger = logging.getLogger(__name__)


def _prefer_cheaper_first() -> bool:
    return (os.environ.get("CERBERUS_SCAFFOLD_COST_ROUTE") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _order_clients(clients: list) -> list:
    """Order scaffolds for query: cost-first when enabled, else primary then others."""
    if not clients:
        return clients
    if _prefer_cheaper_first():
        return sorted(
            clients,
            key=lambda c: (
                float(c.cost_estimate()),
                latency_ema(c.spec.id) if latency_ema(c.spec.id) is not None else 1e9,
                c.spec.id,
            ),
        )
    # Prefer env primary first for stable consensus pairing.
    primary = build_primary_scaffold()
    if not primary:
        return clients
    pid = primary.spec.id
    head = [c for c in clients if c.spec.id == pid]
    tail = [c for c in clients if c.spec.id != pid]
    return head + tail


def complete_for_plan(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
) -> tuple[Optional[str], dict[str, Any]]:
    """
    Return (content, meta). When multi-scaffold is on, query enabled scaffolds
    and return primary/cheapest content plus raw texts in meta for consensus.
    """
    meta: dict[str, Any] = {"mode": "single"}
    if not multi_scaffold_enabled():
        return llm.chat_completion(messages, temperature=temperature), meta

    clients = build_enabled_clients()
    if not clients:
        return llm.chat_completion(messages, temperature=temperature), meta

    temp = 0.3 if temperature is None else temperature
    order = _order_clients(clients)

    texts: list[tuple[str, Optional[str]]] = []
    costs: dict[str, float] = {}
    for client in order:
        costs[client.spec.id] = float(client.cost_estimate())
        texts.append((client.spec.id, client.complete(messages, temperature=temp)))

    meta = {
        "mode": "multi",
        "scaffolds": [t[0] for t in texts],
        "raw": {sid: (txt or "")[:2000] for sid, txt in texts},
        "cost_route": _prefer_cheaper_first(),
        "cost_usd": costs,
    }
    # Prefer primary non-empty; else first with text (respects cost order when routed).
    primary = build_primary_scaffold()
    primary_id = primary.spec.id if primary else (order[0].spec.id if order else None)
    if primary_id and not _prefer_cheaper_first():
        for sid, txt in texts:
            if sid == primary_id and txt and txt.strip():
                meta["chosen_scaffold"] = sid
                meta["chosen_reason"] = "primary"
                return txt, meta
    for sid, txt in texts:
        if txt and txt.strip():
            meta["chosen_scaffold"] = sid
            meta["chosen_reason"] = "cost_route" if _prefer_cheaper_first() else "first_ok"
            return txt, meta
    return None, meta


def parse_candidates(
    raw_by_scaffold: dict[str, str],
) -> list[dict[str, Any]]:
    out = []
    for sid, text in raw_by_scaffold.items():
        parsed = llm.parse_json_object(text or "")
        if parsed:
            parsed = dict(parsed)
            parsed["scaffold_id"] = sid
            out.append(parsed)
    return out
