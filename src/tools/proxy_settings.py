"""Runtime proxy credential settings (Redis-backed, env fallback)."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import quote, unquote, urlparse

ALLOWED_PROTOCOLS = frozenset({"http", "https", "socks5h"})

REDIS_KEY = "cerberus:proxy:settings"

_REQUIRED = ("username", "password", "host", "port", "protocol")
_memory_store: dict[str, str] = {}


def _memory_clear() -> None:
    _memory_store.clear()


def _use_memory() -> bool:
    return os.getenv("CERBERUS_PROXY_SETTINGS_BACKEND", "").lower() in {
        "1",
        "true",
        "yes",
        "memory",
    }


def _redis_client():
    from orchestrator.celeryconfig import REDIS_URL
    import redis

    return redis.from_url(REDIS_URL, decode_responses=True)


def parse_proxy_url(url: str) -> dict[str, Any]:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("proxy_url is required")
    parsed = urlparse(raw)
    protocol = (parsed.scheme or "http").lower()
    if protocol not in ALLOWED_PROTOCOLS:
        raise ValueError(f"unsupported protocol: {protocol}")
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    host = parsed.hostname or ""
    if not username:
        raise ValueError("proxy_url missing username")
    if not password:
        raise ValueError("proxy_url missing password")
    if not host:
        raise ValueError("proxy_url missing host")
    port = parsed.port
    if port is None:
        port = 7777
    return {
        "username": username,
        "password": password,
        "host": host,
        "port": int(port),
        "protocol": protocol,
    }


def merge_put_body(body: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if existing:
        merged.update(
            {
                "username": existing.get("username"),
                "password": existing.get("password"),
                "host": existing.get("host"),
                "port": existing.get("port"),
                "protocol": existing.get("protocol"),
            }
        )

    proxy_url = body.get("proxy_url")
    if isinstance(proxy_url, str) and proxy_url.strip():
        merged.update(parse_proxy_url(proxy_url))

    if "username" in body and body["username"] is not None and str(body["username"]).strip():
        merged["username"] = str(body["username"]).strip()
    if "host" in body and body["host"] is not None and str(body["host"]).strip():
        merged["host"] = str(body["host"]).strip()
    if "protocol" in body and body["protocol"] is not None and str(body["protocol"]).strip():
        merged["protocol"] = str(body["protocol"]).strip().lower()
    if "port" in body and body["port"] is not None and str(body["port"]).strip() != "":
        merged["port"] = int(body["port"])

    password = body.get("password")
    if password is not None and str(password) != "":
        merged["password"] = str(password)
    elif not merged.get("password"):
        raise ValueError("password is required")

    username = (merged.get("username") or "").strip()
    host = (merged.get("host") or "").strip()
    protocol = (merged.get("protocol") or "http").strip().lower()
    port = merged.get("port")
    password_final = merged.get("password") or ""

    if not username:
        raise ValueError("username is required")
    if not host:
        raise ValueError("host is required")
    if protocol not in ALLOWED_PROTOCOLS:
        raise ValueError(f"unsupported protocol: {protocol}")
    if port is None:
        raise ValueError("port is required")
    if not password_final:
        raise ValueError("password is required")

    return {
        "username": username,
        "password": password_final,
        "host": host,
        "port": int(port),
        "protocol": protocol,
    }


def save_settings(data: dict[str, Any]) -> None:
    payload = {
        "username": data["username"],
        "password": data["password"],
        "host": data["host"],
        "port": int(data["port"]),
        "protocol": data["protocol"],
    }
    raw = json.dumps(payload)
    if _use_memory():
        _memory_store[REDIS_KEY] = raw
        return
    client = _redis_client()
    client.set(REDIS_KEY, raw)


def load_settings() -> dict[str, Any] | None:
    if _use_memory():
        raw = _memory_store.get(REDIS_KEY)
    else:
        try:
            raw = _redis_client().get(REDIS_KEY)
        except Exception:
            return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("username") or not data.get("password"):
        return None
    return {
        "username": str(data["username"]),
        "password": str(data["password"]),
        "host": str(data.get("host") or "pr.oxylabs.io"),
        "port": int(data.get("port") or 7777),
        "protocol": str(data.get("protocol") or "http"),
    }


def clear_settings() -> None:
    if _use_memory():
        _memory_store.pop(REDIS_KEY, None)
        return
    _redis_client().delete(REDIS_KEY)


def _env_credentials() -> dict[str, Any] | None:
    username = os.getenv("OXYLABS_PROXY_USERNAME")
    password = os.getenv("OXYLABS_PROXY_PASSWORD")
    if not username or not password:
        return None
    return {
        "username": username,
        "password": password,
        "host": os.getenv("OXYLABS_PROXY_HOST", "pr.oxylabs.io"),
        "port": int(os.getenv("OXYLABS_PROXY_PORT", "7777")),
        "protocol": os.getenv("OXYLABS_PROXY_PROTOCOL", "http"),
        "source": "env",
    }


def load_credentials() -> dict[str, Any] | None:
    redis_creds = load_settings()
    if redis_creds:
        return {**redis_creds, "source": "redis"}
    return _env_credentials()


def public_view(creds: dict[str, Any] | None, *, source: str) -> dict[str, Any]:
    if not creds:
        return {
            "configured": False,
            "source": "none",
            "username": "",
            "password_set": False,
            "host": "",
            "port": None,
            "protocol": "http",
            "proxy_url_redacted": "",
        }
    protocol = creds.get("protocol") or "http"
    if protocol not in ALLOWED_PROTOCOLS:
        protocol = "http"
    host = creds.get("host") or ""
    port = int(creds.get("port") or 7777)
    username = creds.get("username") or ""
    password = creds.get("password") or ""
    scheme = "socks5h" if protocol == "socks5h" else "http"
    from tools.proxy_config import redact_proxy_url

    full = (
        f"{scheme}://{quote(username, safe='')}:{quote(password, safe='')}@{host}:{port}"
    )
    return {
        "configured": bool(username and password),
        "source": source,
        "username": username,
        "password_set": bool(password),
        "host": host,
        "port": port,
        "protocol": protocol,
        "proxy_url_redacted": redact_proxy_url(full),
    }
