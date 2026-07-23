"""Shared helpers for OSINT scrape wrappers (seed args, domain/username pickers)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from orchestrator.osint.breach_service import seeds_from_target_and_args

_DOMAIN_RE = re.compile(
    r"^(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?(?:/.*)?$",
    re.I,
)


def strip_osint_seed_args(args: list[str] | None) -> list[str]:
    argv = list(args or [])
    out: list[str] = []
    skip_next = False
    for token in argv:
        if skip_next:
            skip_next = False
            continue
        if token in {"--seeds", "--osint-seeds"}:
            skip_next = True
            continue
        out.append(token)
    return out


def parse_seeds(target: str, args: list[str] | None) -> list[dict[str, str]]:
    return seeds_from_target_and_args(target, args)


def looks_like_domain(value: str) -> bool:
    text = (value or "").strip()
    if not text or " " in text:
        return False
    return bool(_DOMAIN_RE.match(text))


def pick_harvest_domain(target: str, seeds: list[dict[str, str]]) -> str:
    for seed in seeds:
        kind = str(seed.get("kind") or "")
        value = str(seed.get("value") or "").strip()
        if kind == "domain" and looks_like_domain(value):
            return _normalize_domain(value)
        if kind == "email" and "@" in value:
            domain = value.split("@", 1)[1].strip().lower()
            if looks_like_domain(domain):
                return _normalize_domain(domain)
    if looks_like_domain(target):
        return _normalize_domain(target)
    return ""


def pick_web_url(target: str, seeds: list[dict[str, str]]) -> str:
    for seed in seeds:
        if str(seed.get("kind") or "") == "social_url":
            value = str(seed.get("value") or "").strip()
            if value:
                return value if "://" in value else f"https://{value.lstrip('/')}"
    domain = pick_harvest_domain(target, seeds)
    if domain:
        return f"https://{domain}"
    text = (target or "").strip()
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return ""


def _normalize_domain(raw: str) -> str:
    text = raw.strip()
    if "://" in text:
        text = urlparse(text).hostname or text
    return text.split("/")[0].split(":")[0]


def _social_handle(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url.lstrip('/')}")
    parts = [p for p in (parsed.path or "").split("/") if p]
    if parts:
        return parts[-1].lstrip("@")
    return ""


def pick_username(target: str, seeds: list[dict[str, str]]) -> str:
    for seed in seeds:
        kind = str(seed.get("kind") or "")
        value = str(seed.get("value") or "").strip()
        if kind == "username" and value:
            return value.lstrip("@")
        if kind == "social_url" and value:
            handle = _social_handle(value)
            if handle and " " not in handle:
                return handle.lstrip("@")
        if kind == "email" and "@" in value:
            local = value.split("@", 1)[0].strip()
            if local and " " not in local and len(local) >= 2:
                return local
    text = (target or "").strip().lstrip("@")
    if text and " " not in text and "@" not in text and len(text) >= 2:
        return text
    return ""


def skip_result(
    tool: str,
    target: str,
    *,
    seeds: list[dict[str, str]] | None = None,
    note: str,
) -> dict[str, Any]:
    return {
        "tool": tool,
        "target": target,
        "seeds": seeds or [],
        "skipped": True,
        "note": note,
        "productive": False,
    }
