"""OpenAI-compatible scaffold client (Firebreak W1)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ScaffoldSpec:
    id: str
    model: str
    base_url: str
    api_key: str = "ollama"
    tasks: tuple[str, ...] = ("plan_phase", "summarize")
    enabled: bool = True
    # USD per 1k tokens (prompt+completion). Local/Ollama defaults to 0.
    cost_per_1k: float = 0.0


def _completions_url(base: str) -> str:
    value = (base or "").strip().rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    if value.endswith("/v1"):
        return f"{value}/chat/completions"
    return f"{value}/v1/chat/completions"


def _float_env(name: str, default: float = 0.0) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


class OpenAICompatibleScaffold:
    def __init__(self, spec: ScaffoldSpec):
        self.spec = spec

    def health(self) -> dict[str, Any]:
        started = time.time()
        url = self.spec.base_url.rstrip("/")
        models_url = url if url.endswith("/v1") else f"{url}/v1"
        models_url = f"{models_url.rstrip('/')}/models"
        try:
            resp = requests.get(
                models_url,
                headers={"Authorization": f"Bearer {self.spec.api_key}"},
                timeout=5,
            )
            ok = resp.status_code < 500
            return {
                "id": self.spec.id,
                "ok": ok,
                "status_code": resp.status_code,
                "latency_ms": int((time.time() - started) * 1000),
                "model": self.spec.model,
                "cost_per_1k": self.spec.cost_per_1k,
            }
        except Exception as exc:
            return {
                "id": self.spec.id,
                "ok": False,
                "error": str(exc),
                "latency_ms": int((time.time() - started) * 1000),
                "model": self.spec.model,
                "cost_per_1k": self.spec.cost_per_1k,
            }

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.3,
        timeout: float = 90.0,
    ) -> Optional[str]:
        url = _completions_url(self.spec.base_url)
        body = {
            "model": self.spec.model,
            "messages": messages,
            "temperature": temperature,
            "think": False,
        }
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.spec.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=timeout,
            )
            resp.raise_for_status()
            message = resp.json()["choices"][0]["message"]
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            reasoning = message.get("reasoning_content")
            return reasoning if isinstance(reasoning, str) else None
        except Exception as exc:
            logger.debug("scaffold %s complete failed: %s", self.spec.id, exc)
            return None

    def cost_estimate(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> float:
        tokens = max(0, int(prompt_tokens)) + max(0, int(completion_tokens))
        if tokens <= 0:
            tokens = 1500
        return (tokens / 1000.0) * float(self.spec.cost_per_1k or 0.0)


def build_from_registry_row(row: dict[str, Any]) -> Optional[OpenAICompatibleScaffold]:
    """Build a client from a registry / marketplace row."""
    base = str(row.get("base_url") or row.get("base_url_hint") or "").strip()
    model = str(row.get("model") or "").strip()
    sid = str(row.get("id") or "").strip()
    if not base or not model or not sid:
        return None
    if row.get("enabled") is False:
        return None
    key_env = str(row.get("api_key_env") or "CERBERUS_LLM_API_KEY").strip()
    api_key = os.environ.get(key_env) or os.environ.get("CERBERUS_LLM_API_KEY") or "ollama"
    try:
        cost = float(row.get("cost_per_1k") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    tasks = row.get("tasks") or ("plan_phase", "summarize")
    if isinstance(tasks, list):
        tasks_t = tuple(str(t) for t in tasks)
    elif isinstance(tasks, tuple):
        tasks_t = tasks
    else:
        tasks_t = ("plan_phase", "summarize")
    return OpenAICompatibleScaffold(
        ScaffoldSpec(
            id=sid[:64],
            model=model[:128],
            base_url=base,
            api_key=api_key,
            tasks=tasks_t,
            enabled=True,
            cost_per_1k=max(0.0, cost),
        )
    )


def build_primary_scaffold() -> Optional[OpenAICompatibleScaffold]:
    base = (os.environ.get("CERBERUS_LLM_BASE_URL") or "").strip()
    if not base:
        return None
    return OpenAICompatibleScaffold(
        ScaffoldSpec(
            id="ollama-firebreak",
            model=os.environ.get("CERBERUS_LLM_MODEL", "cerberus-firebreak"),
            base_url=base,
            api_key=os.environ.get("CERBERUS_LLM_API_KEY", "ollama"),
            cost_per_1k=_float_env("CERBERUS_LLM_COST_PER_1K", 0.0),
        )
    )


def build_fallback_scaffold() -> Optional[OpenAICompatibleScaffold]:
    """Second scaffold: base weights or explicit fallback model on same endpoint."""
    base = (os.environ.get("CERBERUS_LLM_BASE_URL") or "").strip()
    if not base:
        return None
    model = (
        os.environ.get("CERBERUS_LLM_FALLBACK_MODEL")
        or os.environ.get("CERBERUS_LLM_BASE_MODEL")
        or "qwen2.5:7b"
    )
    primary = os.environ.get("CERBERUS_LLM_MODEL", "cerberus-firebreak")
    if model == primary:
        return None
    return OpenAICompatibleScaffold(
        ScaffoldSpec(
            id="ollama-fallback",
            model=model,
            base_url=base,
            api_key=os.environ.get("CERBERUS_LLM_API_KEY", "ollama"),
            cost_per_1k=_float_env("CERBERUS_LLM_FALLBACK_COST_PER_1K", 0.0),
        )
    )


def build_extra_scaffold() -> Optional[OpenAICompatibleScaffold]:
    """Optional third OpenAI-compat scaffold (paid API / remote vLLM)."""
    base = (os.environ.get("CERBERUS_SCAFFOLD_EXTRA_BASE_URL") or "").strip()
    model = (os.environ.get("CERBERUS_SCAFFOLD_EXTRA_MODEL") or "").strip()
    if not base or not model:
        return None
    key_env = (
        os.environ.get("CERBERUS_SCAFFOLD_EXTRA_API_KEY_ENV") or "CERBERUS_SCAFFOLD_EXTRA_API_KEY"
    ).strip()
    api_key = (
        os.environ.get(key_env)
        or os.environ.get("CERBERUS_SCAFFOLD_EXTRA_API_KEY")
        or "ollama"
    )
    return OpenAICompatibleScaffold(
        ScaffoldSpec(
            id=(os.environ.get("CERBERUS_SCAFFOLD_EXTRA_ID") or "extra-openai").strip()[:64],
            model=model[:128],
            base_url=base,
            api_key=api_key,
            cost_per_1k=_float_env("CERBERUS_SCAFFOLD_EXTRA_COST_PER_1K", 0.002),
        )
    )
