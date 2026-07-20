"""OpenAI-compatible LLM client with graceful failure."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


def llm_configured() -> bool:
    return bool((os.environ.get("CERBERUS_LLM_BASE_URL") or "").strip())


def completions_url(base: Optional[str] = None) -> Optional[str]:
    """Normalize CERBERUS_LLM_BASE_URL to .../v1/chat/completions."""
    value = (base if base is not None else os.environ.get("CERBERUS_LLM_BASE_URL") or "").strip()
    if not value:
        return None
    value = value.rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return f"{value}/chat/completions"
    return f"{value}/v1/chat/completions"


def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    timeout: float = 60.0,
) -> Optional[str]:
    """
    Call an OpenAI-compatible /v1/chat/completions endpoint.
    Returns assistant content string, or None if unavailable/failed.
    """
    url = completions_url()
    if not url:
        return None
    model = os.environ.get("CERBERUS_LLM_MODEL", "llama3.2")
    api_key = os.environ.get("CERBERUS_LLM_API_KEY", "ollama")
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.debug("LLM chat_completion failed: %s", exc)
        return None


def parse_json_object(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None
