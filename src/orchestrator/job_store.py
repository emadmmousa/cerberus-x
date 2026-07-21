"""Shared playbook job store (Firebreak W4.5 HA).

In-process dict for speed; mirrors to Redis so orchestrator replicas can
read mission status. Nested mutations require ``persist(job_id)`` (or the
helpers call it after phase updates).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator, MutableMapping
from typing import Any, Optional

logger = logging.getLogger(__name__)

PREFIX = "firebreak:job:"
DEFAULT_TTL = int(os.environ.get("FIREBREAK_JOB_TTL_SECONDS") or "86400")


def _redis():
    try:
        from utils.redis_utils import get_redis

        return get_redis()
    except Exception:
        return None


class PlaybookJobStore(MutableMapping):
    def __init__(self, ttl: int = DEFAULT_TTL) -> None:
        self._local: dict[str, dict[str, Any]] = {}
        self._ttl = max(60, int(ttl))

    def _rkey(self, job_id: str) -> str:
        return f"{PREFIX}{job_id}"

    def _redis_set(self, job_id: str, value: dict[str, Any]) -> None:
        r = _redis()
        if r is None:
            return
        try:
            payload = json.dumps(value, default=str)
            if hasattr(r, "setex"):
                r.setex(self._rkey(job_id), self._ttl, payload)
            else:
                r.set(self._rkey(job_id), payload)
        except Exception as exc:
            logger.debug("job store redis set skipped: %s", exc)

    def _redis_get(self, job_id: str) -> Optional[dict[str, Any]]:
        r = _redis()
        if r is None:
            return None
        try:
            raw = r.get(self._rkey(job_id))
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.debug("job store redis get skipped: %s", exc)
            return None

    def persist(self, job_id: str) -> None:
        """Flush local job dict to Redis after nested mutations."""
        if job_id in self._local:
            self._redis_set(job_id, self._local[job_id])

    def __getitem__(self, job_id: str) -> dict[str, Any]:
        if job_id in self._local:
            return self._local[job_id]
        remote = self._redis_get(job_id)
        if remote is None:
            raise KeyError(job_id)
        self._local[job_id] = remote
        return remote

    def __setitem__(self, job_id: str, value: dict[str, Any]) -> None:
        data = dict(value)
        self._local[job_id] = data
        self._redis_set(job_id, data)

    def __delitem__(self, job_id: str) -> None:
        self._local.pop(job_id, None)
        r = _redis()
        if r is not None:
            try:
                r.delete(self._rkey(job_id))
            except Exception:
                pass

    def __iter__(self) -> Iterator[str]:
        return iter(self._local)

    def __len__(self) -> int:
        return len(self._local)

    def __contains__(self, job_id: object) -> bool:
        if not isinstance(job_id, str):
            return False
        if job_id in self._local:
            return True
        return self._redis_get(job_id) is not None

    def list_summaries(
        self, *, org_id: Optional[str] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Return recent in-process (+ hydrated) job summaries for an org."""
        rows: list[dict[str, Any]] = []
        # Prefer local keys; also scan Redis when available.
        ids = set(self._local.keys())
        r = _redis()
        if r is not None:
            try:
                for key in r.scan_iter(match=f"{PREFIX}*", count=200):
                    raw = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
                    ids.add(raw[len(PREFIX) :])
            except Exception as exc:
                logger.debug("job store scan skipped: %s", exc)
        for job_id in ids:
            try:
                job = self[job_id]
            except KeyError:
                continue
            if org_id is not None and str(job.get("org_id") or "default") != str(org_id):
                continue
            rows.append(
                {
                    "task_id": job.get("task_id") or job_id,
                    "target": job.get("target"),
                    "state": job.get("state"),
                    "ai_mode": bool(job.get("ai_mode")),
                    "posture": job.get("posture") or (job.get("ai") or {}).get("posture"),
                    "org_id": job.get("org_id"),
                    "nl_goal": job.get("nl_goal") or (job.get("ai") or {}).get("goal"),
                    "error": job.get("error"),
                }
            )
        # Newest-looking first: uuid4 is time-ish but not sortable; keep insertion-ish reverse local order
        rows.sort(key=lambda r: r.get("task_id") or "", reverse=True)
        return rows[: max(1, min(int(limit), 200))]


# Process-wide store used by dashboard + runner (HA via Redis mirror).
playbook_jobs = PlaybookJobStore()
