"""Optional Flask-Limiter integration with safe no-op fallback."""

from __future__ import annotations

import logging
import os

from utils.redis_utils import get_redis

logger = logging.getLogger(__name__)


def get_dynamic_limit() -> str:
    redis = get_redis()
    try:
        threat_score = int(redis.get("global_threat_score") or 0)
    except Exception:
        threat_score = 0
    if threat_score > 80:
        return "20 per minute"
    if threat_score > 50:
        return "50 per minute"
    return "100 per minute"


class _NoopLimiter:
    def init_app(self, app):
        logger.info("flask-limiter not installed; rate limiting disabled")

    def limit(self, *args, **kwargs):
        def deco(fn):
            return fn

        return deco

    def request_filter(self, fn):
        return fn


def _build_limiter():
    if os.environ.get("CERBERUS_RATE_LIMIT_ENABLED", "true").lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return _NoopLimiter()
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        lim = Limiter(
            key_func=get_remote_address,
            storage_uri=redis_url,
            default_limits=[get_dynamic_limit()],
        )
        return lim
    except Exception as exc:
        logger.warning("rate limiter unavailable: %s", exc)
        return _NoopLimiter()


limiter = _build_limiter()
