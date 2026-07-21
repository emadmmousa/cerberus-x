from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)
DEFAULT_SECRET = "cerberus-x-secret"
INSECURE_SECRETS = frozenset({"cerberus-x-secret", "change-me", ""})


def secret_key_is_insecure(secret: str | None = None) -> bool:
    value = secret if secret is not None else os.environ.get("SECRET_KEY", DEFAULT_SECRET)
    return (value or "") in INSECURE_SECRETS


def configure_sessions(app, *, force_cookie: bool = False) -> dict[str, Any]:
    secure = (os.environ.get("CERBERUS_SESSION_SECURE") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = secure
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

    if secret_key_is_insecure(app.config.get("SECRET_KEY")):
        logger.warning(
            "SECRET_KEY is the insecure default; set a strong SECRET_KEY in production"
        )

    if force_cookie:
        return {"backend": "cookie", "secure": secure}

    try:
        from flask_session import Session
        from utils.redis_utils import get_redis
        import redis as redis_lib

        client = get_redis()
        if not isinstance(client, redis_lib.Redis):
            logger.warning("Redis sessions unavailable (memory fallback); using cookies")
            return {"backend": "cookie", "secure": secure}

        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = client
        app.config["SESSION_KEY_PREFIX"] = "cerberus:sess:"
        app.config["SESSION_USE_SIGNER"] = True
        app.config["SESSION_PERMANENT"] = False
        Session(app)
        return {"backend": "redis", "secure": secure}
    except Exception as exc:
        logger.warning("Flask-Session Redis setup failed (%s); using cookies", exc)
        return {"backend": "cookie", "secure": secure}
