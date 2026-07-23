"""Normalize operator targets across URL/host variants for missions."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from tools.wrappers._web_url import canonicalize_web_url

_IP_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_HOSTLIKE_RE = re.compile(
    r"^(?:https?://)?"
    r"((?:[a-z0-9-]+\.)+[a-z]{2,}|(?:\d{1,3}\.){3}\d{1,3})"
    r"(?::\d+)?(?:/.*)?$",
    re.I,
)


def is_web_engagement_target(raw: str) -> bool:
    """True when the operator target is a hostname/URL (not an OSINT person identifier)."""
    text = (raw or "").strip().rstrip(".,)]")
    if not text:
        return False
    if "://" in text:
        return True
    if _IP_RE.match(text):
        return True
    # Names, emails, phones, and free text are not web engagement targets.
    if " " in text or "@" in text:
        return False
    if "." in text and _HOSTLIKE_RE.match(text):
        return True
    return False


def normalize_engagement_target(raw: str) -> dict[str, str | list[str]]:
    """Return canonical host/URLs for any operator input variant."""
    text = (raw or "").strip().rstrip(".,)]")
    if not text or not is_web_engagement_target(text):
        return {}

    probe = text if "://" in text else f"https://{text.lstrip('/')}"
    try:
        host = (urlparse(probe).hostname or "").lower().strip(".")
    except Exception:
        host = ""
    if not host:
        return {}

    apex = host[4:] if host.startswith("www.") else host
    www = host if host.startswith("www.") else f"www.{apex}"

    try:
        https_url = canonicalize_web_url(apex, probe=True)
    except ValueError:
        https_url = f"https://{apex}"

    https_www = f"https://{www}"
    http_url = f"http://{apex}"
    http_www = f"http://{www}"

    variants: list[str] = []
    for item in (
        text,
        apex,
        www,
        https_url,
        https_www,
        http_url,
        http_www,
        f"https://{apex}/",
        f"https://{www}/",
    ):
        v = str(item).strip()
        if v and v not in variants:
            variants.append(v)

    return {
        "raw": text,
        "host": apex,
        "www_host": www,
        "scope_host": host,
        "https_url": https_url.rstrip("/") or f"https://{apex}",
        "https_www": https_www.rstrip("/"),
        "variants": variants,
    }


def hydrate_plan_targets(plan: dict, ctx: dict[str, str | list[str]]) -> dict:
    """Substitute target placeholders inside a seed plan."""
    if not plan or not ctx:
        return plan
    host = str(ctx.get("host") or "")
    https = str(ctx.get("https_url") or f"https://{host}")
    https_www = str(ctx.get("https_www") or f"https://www.{host}")
    repl = {
        "{target}": https,
        "{url}": https,
        "{https}": https,
        "{domain}": host,
        "{host}": host,
        "{www}": https_www,
        "{apex}": https,
    }
    out = dict(plan)
    phases: list[dict] = []
    for phase in plan.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        tools_out: list[dict] = []
        for entry in phase.get("tools") or []:
            if not isinstance(entry, dict):
                continue
            args = []
            for arg in entry.get("args") or []:
                s = str(arg)
                for key, val in repl.items():
                    s = s.replace(key, val)
                args.append(s)
            tools_out.append({**entry, "args": args})
        phases.append({**phase, "tools": tools_out})
    out["phases"] = phases
    out["target_context"] = ctx
    return out
