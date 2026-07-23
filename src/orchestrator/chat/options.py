"""Per-message chat agent options (model, posture, think, search, attachments)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from orchestrator.ai.posture import DEFAULT_POSTURE, normalize_posture

MAX_ATTACHMENT_BYTES = 96_000
MAX_ATTACHMENTS = 3


@dataclass
class ChatAttachment:
    name: str
    content: str
    content_type: str = "text/plain"

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "content": self.content,
            "type": self.content_type,
        }


@dataclass
class ChatAgentOptions:
    deep_think: bool = False
    web_search: bool = False
    model: str | None = None
    posture: str = DEFAULT_POSTURE
    attachments: list[ChatAttachment] = field(default_factory=list)
    osint_seeds: list[dict[str, str]] = field(default_factory=list)
    # Auto Run (default on): a ready plan may auto-launch on execute intent.
    # Always Run (default off): auto-launch even plan-only ready proposals.
    auto_run: bool = True
    always_run: bool = False
    creative_mode: bool = True

    def resolved_model(self) -> str:
        from orchestrator.ai.llm import chat_model

        raw = (self.model or "").strip()
        return raw or chat_model()

    def normalized_posture(self) -> str:
        return normalize_posture(self.posture)

    def as_dict(self) -> dict[str, Any]:
        return {
            "deep_think": self.deep_think,
            "web_search": self.web_search,
            "model": self.resolved_model(),
            "posture": self.normalized_posture(),
            "attachments": [a.as_dict() for a in self.attachments],
            "osint_seeds": list(self.osint_seeds),
            "auto_run": self.auto_run,
            "always_run": self.always_run,
            "creative_mode": self.creative_mode,
        }


def _clip_text(raw: str, limit: int = MAX_ATTACHMENT_BYTES) -> str:
    text = str(raw or "")
    if len(text.encode("utf-8")) <= limit:
        return text
    return text.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def parse_chat_options(body: dict[str, Any] | None) -> ChatAgentOptions:
    body = body or {}
    opts = body.get("options") if isinstance(body.get("options"), dict) else body
    if not isinstance(opts, dict):
        opts = {}

    attachments: list[ChatAttachment] = []
    raw_atts = opts.get("attachments") or body.get("attachments") or []
    if isinstance(raw_atts, list):
        for row in raw_atts[:MAX_ATTACHMENTS]:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "attachment.txt").strip()[:120]
            content = _clip_text(str(row.get("content") or ""))
            if not content.strip():
                continue
            attachments.append(
                ChatAttachment(
                    name=name,
                    content=content,
                    content_type=str(row.get("type") or row.get("content_type") or "text/plain")[:80],
                )
            )

    model = str(opts.get("model") or "").strip() or None
    posture = str(opts.get("posture") or DEFAULT_POSTURE)

    from orchestrator.osint.seeds import normalize_osint_seeds

    osint_seeds = normalize_osint_seeds(opts.get("osint_seeds") or body.get("osint_seeds"))

    def _flag(key: str, default: bool = False) -> bool:
        val = opts.get(key)
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).strip().lower() in {"1", "true", "yes", "on"}

    return ChatAgentOptions(
        deep_think=_flag("deep_think"),
        web_search=_flag("web_search"),
        model=model,
        posture=posture,
        attachments=attachments,
        osint_seeds=osint_seeds,
        auto_run=_flag("auto_run", default=True),
        always_run=_flag("always_run", default=False),
        creative_mode=_flag("creative_mode", default=True),
    )


def list_chat_models() -> list[dict[str, str]]:
    """Models the operator can pick in chat."""
    seen: set[str] = set()
    rows: list[dict[str, str]] = []

    def add(model_id: str, label: str | None = None) -> None:
        mid = (model_id or "").strip()
        if not mid or mid in seen:
            return
        seen.add(mid)
        rows.append({"id": mid, "label": label or mid})

    add(os.environ.get("FIREBREAK_LLM_CHAT_MODEL") or "", "Chat default")
    add(os.environ.get("FIREBREAK_LLM_MODEL") or "firebreak", "Mission model")
    add(os.environ.get("FIREBREAK_LLM_FALLBACK_MODEL") or "", "Fallback")
    add(os.environ.get("FIREBREAK_LLM_BASE_MODEL") or "", "Base weights")

    base = (os.environ.get("FIREBREAK_LLM_BASE_URL") or "").strip().rstrip("/")
    if base:
        try:
            import requests

            tags_url = base.replace("/v1", "").rstrip("/") + "/api/tags"
            if base.endswith("/v1"):
                tags_url = base[:-3].rstrip("/") + "/api/tags"
            resp = requests.get(tags_url, timeout=3)
            if resp.ok:
                for row in resp.json().get("models") or []:
                    name = str(row.get("name") or "").strip()
                    add(name, name)
        except Exception:
            pass

    if not rows:
        add("firebreak", "Firebreak")
    return rows
