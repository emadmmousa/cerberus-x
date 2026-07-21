"""Local-first audit logger (S3/Splunk optional)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _safe_request_ip() -> str:
    try:
        from flask import has_request_context, request

        if has_request_context():
            return request.remote_addr or "unknown"
    except Exception:
        pass
    return "unknown"


def _safe_actor() -> dict[str, Any]:
    """Best-effort acting identity (user / role / org) from the session."""
    try:
        from flask import has_request_context, session

        if has_request_context():
            return {
                "user": session.get("user") or "anonymous",
                "role": session.get("role"),
                "org_id": session.get("org_id"),
            }
    except Exception:
        pass
    return {"user": "system", "role": None, "org_id": None}


def audit_log(event_type: str, data: Any, severity: str = "info") -> dict:
    actor = _safe_actor()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "data": data,
        "severity": severity,
        "source_ip": _safe_request_ip(),
        "actor": actor.get("user"),
        "actor_role": actor.get("role"),
        "actor_org": actor.get("org_id"),
    }
    entry_json = json.dumps(entry, default=str)
    logger.info("audit %s %s", event_type, entry_json)

    try:
        from utils.redis_utils import get_redis

        redis = get_redis()
        redis.rpush("audit:recent", entry_json)
        redis.ltrim("audit:recent", -1000, -1)
    except Exception as exc:
        logger.debug("audit redis write skipped: %s", exc)

    # Optional sinks — never fail the request path.
    try:
        from utils.config import get_config

        cfg = get_config()
        webhook = (cfg.get("ALERT_WEBHOOK") or "").strip()
        if severity in {"critical", "high"} and webhook:
            import requests

            requests.post(webhook, json=entry, timeout=1)
    except Exception as exc:
        logger.debug("audit webhook skipped: %s", exc)

    try:
        from utils.config import get_config

        cfg = get_config()
        hec = (cfg.get("SPLUNK_HEC_URL") or "").strip()
        token = (cfg.get("SPLUNK_HEC_TOKEN") or "").strip()
        if hec and token:
            import requests

            requests.post(
                hec,
                json={"event": entry, "sourcetype": "firebreak-audit"},
                headers={"Authorization": f"Splunk {token}"},
                timeout=2,
            )
    except Exception as exc:
        logger.debug("audit splunk skipped: %s", exc)

    # Optional Elasticsearch sink (Firebreak W4.4).
    try:
        from utils.config import get_config

        cfg = get_config()
        es_url = (cfg.get("ELASTICSEARCH_URL") or os.environ.get("ELASTICSEARCH_URL") or "").strip()
        es_index = (
            cfg.get("FIREBREAK_AUDIT_ES_INDEX")
            or os.environ.get("FIREBREAK_AUDIT_ES_INDEX")
            or "firebreak-audit"
        ).strip()
        if es_url and (os.environ.get("FIREBREAK_AUDIT_ES") or "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            import requests

            requests.post(
                f"{es_url.rstrip('/')}/{es_index}/_doc",
                json=entry,
                timeout=2,
                headers={"Content-Type": "application/json"},
            )
    except Exception as exc:
        logger.debug("audit elasticsearch skipped: %s", exc)

    return entry


def recent_audit(limit: int = 50) -> list[dict]:
    try:
        from utils.redis_utils import get_redis

        redis = get_redis()
        # MemoryRedis has no lrange — emulate via llen/get if needed.
        if hasattr(redis, "lrange"):
            rows = redis.lrange("audit:recent", -limit, -1)
        else:
            rows = list(getattr(redis, "_lists", {}).get("audit:recent", []))[-limit:]
        out = []
        for row in rows:
            try:
                out.append(json.loads(row))
            except Exception:
                continue
        return out
    except Exception:
        return []
