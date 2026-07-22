"""OpenAI-compatible LLM client with graceful failure."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import requests

from orchestrator.ai.prompts import llm_unrestricted, planner_temperature

logger = logging.getLogger(__name__)


def llm_configured() -> bool:
    return bool((os.environ.get("FIREBREAK_LLM_BASE_URL") or "").strip())


def chat_model() -> str:
    """Model for conversational (natural-language) chat.

    Defaults to the same model as missions (``firebreak``) so a single 7B model
    stays resident — loading a second model alongside it OOM-kills llama-server
    on memory-constrained hosts. The baked-in JSON planner persona is overridden
    at call time by the advisor system prompt. Set FIREBREAK_LLM_CHAT_MODEL to a
    lighter model (e.g. llama3.2:latest) only if you have RAM headroom and prefer
    speed over uncensored security depth.
    """
    return (
        os.environ.get("FIREBREAK_LLM_CHAT_MODEL")
        or os.environ.get("FIREBREAK_LLM_MODEL")
        or "firebreak"
    )


def completions_url(base: Optional[str] = None) -> Optional[str]:
    """Normalize FIREBREAK_LLM_BASE_URL to .../v1/chat/completions."""
    value = (base if base is not None else os.environ.get("FIREBREAK_LLM_BASE_URL") or "").strip()
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
    temperature: float | None = None,
    timeout: float = 90.0,
    model: Optional[str] = None,
) -> Optional[str]:
    """
    Call an OpenAI-compatible /v1/chat/completions endpoint.
    Returns assistant content string, or None if unavailable/failed.
    """
    url = completions_url()
    if not url:
        return None
    model = model or os.environ.get("FIREBREAK_LLM_MODEL", "firebreak")
    api_key = os.environ.get("FIREBREAK_LLM_API_KEY", "ollama")
    temp = planner_temperature() if temperature is None else temperature
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temp,
    }
    # Ollama OpenAI-compat accepts these; ignored by strict OpenAI servers.
    if llm_unrestricted():
        body["top_p"] = float(os.environ.get("FIREBREAK_LLM_TOP_P", "0.95"))
        body["frequency_penalty"] = 0.0
        body["presence_penalty"] = 0.1
    # DeepSeek Instant / R1-style models: keep planner replies JSON-clean.
    think_raw = (os.environ.get("FIREBREAK_LLM_THINK") or "false").strip().lower()
    body["think"] = think_raw in {"1", "true", "yes", "on"}
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data["choices"][0]["message"]
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        # Some thinking models put the final answer only in reasoning_content.
        reasoning = message.get("reasoning_content")
        return reasoning if isinstance(reasoning, str) else None
    except Exception as exc:
        logger.debug("LLM chat_completion failed: %s", exc)
        return None


def chat_completion_stream(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    timeout: float = 120.0,
    model: Optional[str] = None,
):
    """Yield assistant content deltas from an OpenAI-compatible streaming endpoint.

    Yields plain text chunks. Silently yields nothing when the LLM is
    unavailable so callers can fall back to a non-streaming path.
    """
    url = completions_url()
    if not url:
        return
    model = model or os.environ.get("FIREBREAK_LLM_MODEL", "firebreak")
    api_key = os.environ.get("FIREBREAK_LLM_API_KEY", "ollama")
    temp = planner_temperature() if temperature is None else temperature
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temp,
        "stream": True,
    }
    if llm_unrestricted():
        body["top_p"] = float(os.environ.get("FIREBREAK_LLM_TOP_P", "0.95"))
        body["presence_penalty"] = 0.1
    think_raw = (os.environ.get("FIREBREAK_LLM_THINK") or "false").strip().lower()
    body["think"] = think_raw in {"1", "true", "yes", "on"}
    try:
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                if line == "[DONE]":
                    break
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            try:
                delta = chunk["choices"][0]["delta"]
            except (KeyError, IndexError, TypeError):
                continue
            piece = delta.get("content") or delta.get("reasoning_content")
            if isinstance(piece, str) and piece:
                yield piece
    except Exception as exc:  # pragma: no cover - network dependent
        logger.debug("LLM chat_completion_stream failed: %s", exc)
        return


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
