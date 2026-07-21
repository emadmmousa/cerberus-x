"""Redis Blackboard — shared mission memory for multi-scaffold (Firebreak W1)."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore


DEFAULT_TTL_SECONDS = 86400
KEY_PREFIX = "bb"


def _client():
    if redis is None:
        raise RuntimeError("redis package not installed")
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(url, decode_responses=True)


def _org_scope(org_id: str | None = None) -> str:
    """Tenant prefix for Blackboard keys (Firebreak W4.3)."""
    if org_id and str(org_id).strip():
        return str(org_id).strip()
    return (
        os.environ.get("CERBERUS_DEFAULT_ORG") or "default"
    ).strip() or "default"


def _key(mission_id: str, name: str, *, org_id: str | None = None) -> str:
    mid = (mission_id or "default").strip() or "default"
    nm = (name or "").strip()
    if not nm:
        raise ValueError("blackboard key name is required")
    org = _org_scope(org_id)
    return f"{KEY_PREFIX}:{org}:{mid}:{nm}"


def put(
    mission_id: str,
    name: str,
    value: Any,
    *,
    ttl: int = DEFAULT_TTL_SECONDS,
    expected_version: int | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Write a value. If expected_version is set, CAS against that version."""
    r = _client()
    org = _org_scope(org_id)
    key = _key(mission_id, name, org_id=org)
    now = time.time()
    raw = r.get(key)
    current_version = 0
    if raw:
        try:
            prev = json.loads(raw)
            current_version = int(prev.get("version") or 0)
        except (TypeError, ValueError, json.JSONDecodeError):
            current_version = 0
        if expected_version is not None and current_version != expected_version:
            return {
                "ok": False,
                "conflict": True,
                "version": current_version,
                "key": name,
                "org_id": org,
            }
    version = current_version + 1
    doc = {
        "mission_id": mission_id,
        "org_id": org,
        "key": name,
        "value": value,
        "version": version,
        "updated_at": now,
    }
    r.set(key, json.dumps(doc), ex=max(1, int(ttl)))
    channel = f"{KEY_PREFIX}:notify:{org}:{mission_id}"
    try:
        r.publish(channel, json.dumps({"key": name, "version": version, "org_id": org}))
    except Exception:
        pass
    return {"ok": True, "conflict": False, "version": version, "key": name, "org_id": org}


def get(
    mission_id: str, name: str, *, org_id: str | None = None
) -> Optional[dict[str, Any]]:
    r = _client()
    raw = r.get(_key(mission_id, name, org_id=org_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def list_keys(mission_id: str, *, org_id: str | None = None) -> list[str]:
    r = _client()
    mid = (mission_id or "default").strip() or "default"
    org = _org_scope(org_id)
    pattern = f"{KEY_PREFIX}:{org}:{mid}:*"
    prefix = f"{KEY_PREFIX}:{org}:{mid}:"
    names: list[str] = []
    for full in r.scan_iter(match=pattern, count=200):
        if full.startswith(prefix):
            names.append(full[len(prefix) :])
    return sorted(names)


def delete(mission_id: str, name: str, *, org_id: str | None = None) -> bool:
    r = _client()
    return bool(r.delete(_key(mission_id, name, org_id=org_id)))
