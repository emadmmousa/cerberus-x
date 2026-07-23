"""DeHashed and LeakCheck breach-intel API clients."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEHASHED_SEARCH_URL = "https://api.dehashed.com/v2/search"
DEHASHED_USER_INFO_URL = "https://api.dehashed.com/v2/info/user"
LEAKCHECK_BASE_URL = "https://leakcheck.io/api/v2/query"

_DEHASHED_MIN_INTERVAL = 0.055  # ~18 req/s — stay under 20/s limit
_dehashed_lock = threading.Lock()
_dehashed_last_call = 0.0

_SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "hashed_password",
        "phash",
    }
)


def _env_key(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def dehashed_api_key() -> str:
    return _env_key("FIREBREAK_DEHASHED_API_KEY", "DEHASHED_API_KEY")


def leakcheck_api_key() -> str:
    return _env_key("FIREBREAK_LEAKCHECK_API_KEY", "LEAKCHECK_API_KEY", "LEAKCHECK_APIKEY")


def breach_intel_enabled() -> bool:
    return os.environ.get("FIREBREAK_BREACH_INTEL_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def provider_status() -> dict[str, Any]:
    dehashed = bool(dehashed_api_key())
    leakcheck = bool(leakcheck_api_key())
    return {
        "enabled": breach_intel_enabled(),
        "dehashed": {"configured": dehashed, "available": dehashed and breach_intel_enabled()},
        "leakcheck": {"configured": leakcheck, "available": leakcheck and breach_intel_enabled()},
        "ready": breach_intel_enabled() and (dehashed or leakcheck),
    }


def _throttle_dehashed() -> None:
    global _dehashed_last_call
    with _dehashed_lock:
        now = time.monotonic()
        wait = _DEHASHED_MIN_INTERVAL - (now - _dehashed_last_call)
        if wait > 0:
            time.sleep(wait)
        _dehashed_last_call = time.monotonic()


def _http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    payload = None
    req_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=payload, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)
    try:
        return status, json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return status, raw[:2000]


def redact_breach_record(record: dict[str, Any]) -> dict[str, Any]:
    """Strip plaintext credentials from breach rows before mission logs."""
    out: dict[str, Any] = {}
    for key, value in record.items():
        if key in _SENSITIVE_FIELDS:
            if isinstance(value, list):
                out[f"{key}_present"] = any(str(v).strip() for v in value)
                out[f"{key}_count"] = len(value)
            elif value:
                out[f"{key}_present"] = True
            continue
        out[key] = value
    return out


def dehashed_search(
    query: str,
    *,
    page: int = 1,
    size: int = 25,
    de_dupe: bool = True,
) -> dict[str, Any]:
    api_key = dehashed_api_key()
    if not api_key:
        return {"provider": "dehashed", "skipped": True, "error": "DEHASHED_API_KEY not configured"}
    if not query.strip():
        return {"provider": "dehashed", "error": "empty query"}

    _throttle_dehashed()
    status, data = _http_json(
        "POST",
        DEHASHED_SEARCH_URL,
        headers={"Dehashed-Api-Key": api_key},
        body={
            "query": query,
            "page": max(1, page),
            "size": min(max(1, size), 100),
            "de_dupe": bool(de_dupe),
            "regex": False,
            "wildcard": False,
        },
    )
    if status == 0:
        return {"provider": "dehashed", "query": query, "error": str(data)}
    if isinstance(data, str):
        return {"provider": "dehashed", "query": query, "status": status, "error": data}
    if status >= 400 or data.get("error"):
        return {
            "provider": "dehashed",
            "query": query,
            "status": status,
            "error": data.get("error") or f"HTTP {status}",
        }

    entries = [redact_breach_record(row) for row in (data.get("entries") or []) if isinstance(row, dict)]
    databases = sorted({str(row.get("database_name") or "").strip() for row in entries if row.get("database_name")})
    return {
        "provider": "dehashed",
        "query": query,
        "status": status,
        "total": int(data.get("total") or 0),
        "returned": len(entries),
        "balance": data.get("balance"),
        "databases": databases[:20],
        "entries": entries,
        "productive": bool(entries) or int(data.get("total") or 0) > 0,
    }


def leakcheck_lookup(
    query: str,
    *,
    query_type: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    api_key = leakcheck_api_key()
    if not api_key:
        return {"provider": "leakcheck", "skipped": True, "error": "LEAKCHECK_API_KEY not configured"}
    normalized_query = query.strip()
    if query_type == "phone":
        normalized_query = re.sub(r"\D", "", normalized_query)
    if len(normalized_query) < 3:
        return {"provider": "leakcheck", "error": "query too short (min 3 chars)"}

    params: dict[str, str | int] = {
        "limit": min(max(1, limit), 100),
        "offset": max(0, offset),
    }
    if query_type:
        params["type"] = query_type
    qs = urllib.parse.urlencode({k: str(v) for k, v in params.items()})
    url = f"{LEAKCHECK_BASE_URL}/{urllib.parse.quote(normalized_query, safe='')}?{qs}"

    status, data = _http_json(
        "GET",
        url,
        headers={"X-API-Key": api_key},
    )
    if status == 0:
        return {"provider": "leakcheck", "query": query, "error": str(data)}
    if isinstance(data, str):
        return {"provider": "leakcheck", "query": query, "status": status, "error": data}
    if status >= 400 or not data.get("success", True):
        return {
            "provider": "leakcheck",
            "query": query,
            "status": status,
            "error": data.get("error") or data.get("message") or f"HTTP {status}",
        }

    rows = []
    for row in data.get("result") or []:
        if isinstance(row, dict):
            rows.append(redact_breach_record(row))
    sources = sorted(
        {
            str((row.get("source") or {}).get("name") or row.get("source") or "").strip()
            for row in rows
            if row.get("source")
        }
    )
    return {
        "provider": "leakcheck",
        "query": query,
        "query_type": query_type,
        "status": status,
        "found": int(data.get("found") or 0),
        "returned": len(rows),
        "quota": data.get("quota"),
        "sources": [s for s in sources if s][:20],
        "entries": rows,
        "productive": bool(rows) or int(data.get("found") or 0) > 0,
    }


def dehashed_user_info() -> dict[str, Any]:
    api_key = dehashed_api_key()
    if not api_key:
        return {"configured": False}
    _throttle_dehashed()
    status, data = _http_json("GET", DEHASHED_USER_INFO_URL, headers={"Dehashed-Api-Key": api_key})
    if status == 0 or isinstance(data, str):
        return {"configured": True, "error": str(data)}
    if status >= 400:
        return {"configured": True, "error": data.get("error") if isinstance(data, dict) else f"HTTP {status}"}
    return {"configured": True, **(data if isinstance(data, dict) else {})}


def build_dehashed_query(kind: str, value: str) -> str:
    kind = (kind or "").strip().lower()
    text = (value or "").strip()
    if kind == "email":
        return text
    if kind == "username":
        return f'username:"{text}"'
    if kind == "mobile":
        digits = re.sub(r"\D", "", text)
        return f'phone:"{digits}"' if digits else text
    if kind == "domain":
        return f'email:"@{text}"'
    if kind == "full_name":
        return f'name:"{text}"'
    if kind == "social_url":
        return f'url:"{text}"'
    return text


def leakcheck_query_type(kind: str) -> str | None:
    mapping = {
        "email": "email",
        "username": "username",
        "mobile": "phone",
        "domain": "domain",
        "full_name": "keyword",
        "social_url": "keyword",
    }
    return mapping.get((kind or "").strip().lower())
