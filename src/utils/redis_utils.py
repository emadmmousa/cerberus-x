"""Redis helper with in-memory fallback for unit tests / offline boot."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Optional


class _MemoryRedis:
    """Minimal subset used by security/session helpers."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._lists: dict[str, list] = {}
        self._sets: dict[str, set] = {}
        self._expiry: dict[str, float] = {}
        self._lock = threading.Lock()

    def _alive(self, key: str) -> bool:
        exp = self._expiry.get(key)
        if exp is not None and time.time() >= exp:
            self._data.pop(key, None)
            self._lists.pop(key, None)
            self._sets.pop(key, None)
            self._expiry.pop(key, None)
            return False
        return True

    def get(self, key: str):
        with self._lock:
            if not self._alive(key):
                return None
            return self._data.get(key)

    def set(self, key: str, value):
        with self._lock:
            self._data[key] = value
            return True

    def setex(self, key: str, ttl, value):
        with self._lock:
            self._data[key] = value
            self._expiry[key] = time.time() + int(ttl)
            return True

    def delete(self, *keys):
        with self._lock:
            for key in keys:
                self._data.pop(key, None)
                self._lists.pop(key, None)
                self._sets.pop(key, None)
                self._expiry.pop(key, None)
            return True

    def rpush(self, key: str, value):
        with self._lock:
            self._lists.setdefault(key, []).append(value)
            return len(self._lists[key])

    def ltrim(self, key: str, start: int, end: int):
        with self._lock:
            items = self._lists.get(key, [])
            # redis ltrim end is inclusive; python slice end exclusive
            if end == -1:
                self._lists[key] = items[start:]
            else:
                self._lists[key] = items[start : end + 1]
            return True

    def llen(self, key: str) -> int:
        with self._lock:
            return len(self._lists.get(key, []))

    def smembers(self, key: str):
        with self._lock:
            return set(self._sets.get(key, set()))

    def sadd(self, key: str, *values):
        with self._lock:
            bucket = self._sets.setdefault(key, set())
            before = len(bucket)
            bucket.update(values)
            return len(bucket) - before

    def hset(self, key: str, mapping=None, **kwargs):
        with self._lock:
            data = self._data.setdefault(key, {})
            if not isinstance(data, dict):
                data = {}
                self._data[key] = data
            if mapping:
                data.update(mapping)
            data.update(kwargs)
            return True

    def hgetall(self, key: str):
        with self._lock:
            val = self._data.get(key) or {}
            return dict(val) if isinstance(val, dict) else {}


_client: Optional[Any] = None


def get_redis():
    """Return a redis client, or an in-memory stand-in if unavailable."""
    global _client
    if _client is not None:
        return _client
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        _client = client
    except Exception:
        _client = _MemoryRedis()
    return _client
