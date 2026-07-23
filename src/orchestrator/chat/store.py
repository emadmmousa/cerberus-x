"""Redis-backed mission chat threads."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any, Optional

from utils.redis_utils import get_redis
from utils.text_encoding import ensure_utf8_text

KEY_PREFIX = "firebreak:chat:"
TTL_SECONDS = 12 * 60 * 60


def _key(chat_id: str) -> str:
    return f"{KEY_PREFIX}{chat_id}"


def create_chat(*, org_id: str = "default") -> str:
    chat_id = secrets.token_urlsafe(16)
    thread = {
        "id": chat_id,
        "org_id": org_id,
        "messages": [],
        "draft": None,
        "mission_ids": [],
        "parse_failures": 0,
        "updated_at": time.time(),
    }
    save_chat(thread)
    return chat_id


def get_chat(chat_id: str) -> Optional[dict[str, Any]]:
    raw = get_redis().get(_key(chat_id))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def save_chat(thread: dict[str, Any]) -> None:
    thread = dict(thread)
    thread["updated_at"] = time.time()
    chat_id = str(thread.get("id") or "")
    if not chat_id:
        raise ValueError("chat id required")
    client = get_redis()
    payload = json.dumps(thread, default=str, ensure_ascii=False)
    key = _key(chat_id)
    if hasattr(client, "setex"):
        client.setex(key, TTL_SECONDS, payload)
    else:
        client.set(key, payload)


def append_message(thread: dict[str, Any], role: str, content: str, **extra: Any) -> dict[str, Any]:
    thinking = extra.pop("thinking_content", None)
    msg = {"role": role, "content": ensure_utf8_text(content), "ts": time.time(), **extra}
    if isinstance(thinking, str) and thinking.strip():
        msg["thinking_content"] = ensure_utf8_text(thinking)
    thread.setdefault("messages", []).append(msg)
    save_chat(thread)
    return msg


def set_draft(thread: dict[str, Any], draft: Optional[dict[str, Any]]) -> None:
    thread["draft"] = draft
    save_chat(thread)


def clear_draft(thread: dict[str, Any]) -> None:
    thread["draft"] = None
    save_chat(thread)


PROCESSING_STALE_SECONDS = 600


def set_processing(thread: dict[str, Any], *, processing: bool) -> None:
    """Mark a thread as actively generating an assistant reply."""
    thread["processing"] = bool(processing)
    if processing:
        thread["processing_started_at"] = time.time()
    else:
        thread.pop("processing_started_at", None)
    save_chat(thread)


def normalize_processing(thread: dict[str, Any] | None) -> dict[str, Any] | None:
    """Clear stale processing flags left by crashed workers or dropped SSE."""
    if not thread or not thread.get("processing"):
        return thread
    started = thread.get("processing_started_at")
    try:
        age = time.time() - float(started or 0)
    except (TypeError, ValueError):
        age = PROCESSING_STALE_SECONDS + 1
    if age > PROCESSING_STALE_SECONDS:
        thread = dict(thread)
        thread["processing"] = False
        thread.pop("processing_started_at", None)
        save_chat(thread)
    return thread
