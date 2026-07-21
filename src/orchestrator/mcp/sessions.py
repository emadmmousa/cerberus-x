"""Redis-backed MCP sessions, audit log, and rate limits."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Optional

_MEMORY: dict[str, Any] = {
    "sessions": {},
    "audit": {},
    "rate": {},
    "session_index": [],
}


def _redis():
    url = os.environ.get("CELERY_BROKER_URL") or os.environ.get(
        "REDIS_URL", "redis://localhost:6379/0"
    )
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


def create_session(target: str, label: Optional[str] = None) -> dict:
    session_id = str(uuid.uuid4())
    payload = {
        "session_id": session_id,
        "target": (target or "").strip(),
        "label": label or "",
        "created_at": time.time(),
    }
    client = _redis()
    if client is not None:
        client.setex(
            f"firebreak:mcp:session:{session_id}",
            86400,
            json.dumps(payload),
        )
        client.lpush("firebreak:mcp:sessions", session_id)
        client.ltrim("firebreak:mcp:sessions", 0, 199)
    else:
        _MEMORY["sessions"][session_id] = payload
        _MEMORY["session_index"].insert(0, session_id)
        _MEMORY["session_index"] = _MEMORY["session_index"][:200]
        _MEMORY["audit"][session_id] = []
    return payload


def get_session(session_id: str) -> Optional[dict]:
    if not session_id:
        return None
    client = _redis()
    if client is not None:
        raw = client.get(f"firebreak:mcp:session:{session_id}")
        if not raw:
            return None
        return json.loads(raw)
    return _MEMORY["sessions"].get(session_id)


def audit(session_id: str, event: dict) -> None:
    entry = {"ts": time.time(), **event}
    client = _redis()
    if client is not None:
        key = f"firebreak:mcp:audit:{session_id}"
        client.lpush(key, json.dumps(entry))
        client.ltrim(key, 0, 499)
        client.expire(key, 86400)
    else:
        _MEMORY["audit"].setdefault(session_id, []).insert(0, entry)
        _MEMORY["audit"][session_id] = _MEMORY["audit"][session_id][:500]


def list_audit(session_id: str, limit: int = 50) -> list[dict]:
    client = _redis()
    if client is not None:
        rows = client.lrange(f"firebreak:mcp:audit:{session_id}", 0, max(limit - 1, 0))
        return [json.loads(r) for r in rows]
    return list(_MEMORY["audit"].get(session_id, [])[:limit])


def list_sessions(limit: int = 20) -> list[dict]:
    client = _redis()
    ids: list[str]
    if client is not None:
        ids = client.lrange("firebreak:mcp:sessions", 0, max(limit - 1, 0))
    else:
        ids = list(_MEMORY["session_index"][:limit])
    out = []
    for sid in ids:
        sess = get_session(sid)
        if not sess:
            continue
        out.append({**sess, "recent_audit": list_audit(sid, limit=5)})
    return out


def check_rate_limit(session_id: str) -> bool:
    """Return True if the call is allowed."""
    limit = int(os.environ.get("FIREBREAK_MCP_RATE_LIMIT_PER_MIN", "30"))
    now = int(time.time())
    window = now // 60
    client = _redis()
    key = f"firebreak:mcp:ratelimit:{session_id}:{window}"
    if client is not None:
        count = client.incr(key)
        if count == 1:
            client.expire(key, 120)
        return count <= limit
    bucket = _MEMORY["rate"].setdefault(session_id, {})
    count = int(bucket.get(window, 0)) + 1
    bucket[window] = count
    # Drop old windows
    for old in list(bucket):
        if old < window - 2:
            del bucket[old]
    return count <= limit


def reset_memory_store() -> None:
    """Test helper."""
    _MEMORY["sessions"].clear()
    _MEMORY["audit"].clear()
    _MEMORY["rate"].clear()
    _MEMORY["session_index"].clear()
