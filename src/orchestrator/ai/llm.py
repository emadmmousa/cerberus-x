"""OpenAI-compatible LLM client with graceful failure."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests


def llm_configured() -> bool:
    return bool((os.environ.get("CERBERUS_LLM_BASE_URL") or "").strip())


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
    base = (os.environ.get("CERBERUS_LLM_BASE_URL") or "").rstrip("/")
    if not base:
        return None
    model = os.environ.get("CERBERUS_LLM_MODEL", "mistral")
    api_key = os.environ.get("CERBERUS_LLM_API_KEY", "ollama")
    url = f"{base}/chat/completions"
    if not url.endswith("/chat/completions"):
        # allow base already including /v1
        if base.endswith("/v1"):
            url = f"{base}/chat/completions"
        else:
            url = f"{base}/v1/chat/completions"
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
    except Exception:
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
