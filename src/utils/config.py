"""Shared configuration helpers (env-backed, no hard deps)."""

from __future__ import annotations

import os
from typing import Any, Optional


class Config:
    """Flask `from_object` compatible settings."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "firebreak-secret")
    VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://vault:8200")
    VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    DB_URI = os.environ.get(
        "DB_URI",
        os.environ.get(
            "DATABASE_URL",
            "postgresql://msf:msf@postgres:5432/msf",
        ),
    )
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
    GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
    LDAP_SERVER = os.environ.get("LDAP_SERVER", "")
    LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "")
    AUDIT_S3_BUCKET = os.environ.get("AUDIT_S3_BUCKET", "")
    AUDIT_S3_PREFIX = os.environ.get("AUDIT_S3_PREFIX", "audit/")
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
    SPLUNK_HEC_URL = os.environ.get("SPLUNK_HEC_URL", "")
    SPLUNK_HEC_TOKEN = os.environ.get("SPLUNK_HEC_TOKEN", "")
    ALERT_WEBHOOK = os.environ.get("ALERT_WEBHOOK", "")
    FIREBREAK_WAF_ENABLED = os.environ.get("FIREBREAK_WAF_ENABLED", "true")
    FIREBREAK_RATE_LIMIT_ENABLED = os.environ.get(
        "FIREBREAK_RATE_LIMIT_ENABLED", "true"
    )


_CONFIG: Optional[dict[str, Any]] = None


def get_config() -> dict[str, Any]:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = {
            key: getattr(Config, key)
            for key in dir(Config)
            if key.isupper() and not key.startswith("_")
        }
        # Also expose raw env for forward-compat.
        _CONFIG.update({k: v for k, v in os.environ.items() if k.isupper()})
    return _CONFIG
