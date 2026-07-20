"""Local-first audit logger (S3/Splunk optional)."""

from __future__ import annotations

import json
import logging
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


def audit_log(event_type: str, data: Any, severity: str = "info") -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "data": data,
        "severity": severity,
        "source_ip": _safe_request_ip(),
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
                json={"event": entry, "sourcetype": "cerberus-audit"},
                headers={"Authorization": f"Splunk {token}"},
                timeout=2,
            )
    except Exception as exc:
        logger.debug("audit splunk skipped: %s", exc)

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
