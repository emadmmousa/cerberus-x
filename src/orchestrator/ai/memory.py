"""Lightweight strategy memory (Phase 3) using SQLite + hash embeddings."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import time
from typing import Optional

from orchestrator.database import DB_PATH


def _connect():
    path = os.environ.get("CERBERUS_DB_PATH", DB_PATH)
    return sqlite3.connect(path)


def init_memory_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_hint TEXT,
                summary TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()


def _embed(text: str, dims: int = 64) -> list[float]:
    """Deterministic bag-of-hash embedding (no external model required)."""
    vec = [0.0] * dims
    tokens = [t.lower() for t in (text or "").replace("/", " ").split() if t]
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:2], "big") % dims
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def remember(summary: str, target_hint: str = "") -> int:
    init_memory_db()
    emb = _embed(f"{target_hint} {summary}")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO ai_memory (target_hint, summary, embedding, created_at) "
            "VALUES (?, ?, ?, ?)",
            (target_hint, summary, json.dumps(emb), time.time()),
        )
        conn.commit()
        return int(cur.lastrowid)


def recall(query: str, k: int = 3) -> list[dict]:
    init_memory_db()
    q = _embed(query)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, target_hint, summary, embedding, created_at FROM ai_memory"
        ).fetchall()
    scored = []
    for row in rows:
        emb = json.loads(row[3])
        scored.append(
            {
                "id": row[0],
                "target_hint": row[1],
                "summary": row[2],
                "score": _cosine(q, emb),
                "created_at": row[4],
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:k]
