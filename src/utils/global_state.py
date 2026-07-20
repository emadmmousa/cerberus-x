"""In-memory / Redis session state for dynamic playbooks."""

from __future__ import annotations

import json
from typing import Any, Optional

from utils.redis_utils import get_redis


def get_state(key: str, default: Any = None) -> Any:
    client = get_redis()
    try:
        raw = client.get(f"state:{key}")
    except Exception:
        return default
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def set_state(key: str, value: Any) -> None:
    client = get_redis()
    try:
        client.setex(f"state:{key}", 86400, json.dumps(value, default=str))
    except Exception:
        # Best-effort; dynamic playbooks still work with empty state.
        pass


def get_session_state(session_id: str) -> dict:
    return get_state(f"session:{session_id}", {}) or {}


def set_session_state(session_id: str, data: dict) -> None:
    existing = get_session_state(session_id)
    existing.update(data or {})
    set_state(f"session:{session_id}", existing)
