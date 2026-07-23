"""Google dork templates and catalog loader for authorized recon."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

TARGET_TOKEN = "TARGET-DOMAIN.COM"

# Core methodology dorks (operator substitutes TARGET-DOMAIN.COM).
CORE_DORKS: tuple[str, ...] = (
    'site:TARGET-DOMAIN.COM',
    'site:*.TARGET-DOMAIN.COM',
    'site:*.TARGET-DOMAIN.COM -site:www.TARGET-DOMAIN.COM',
    'site:TARGET-DOMAIN.COM (inurl:admin OR inurl:login OR inurl:signin OR inurl:auth)',
    'site:TARGET-DOMAIN.COM (ext:sql OR ext:bak OR ext:backup OR ext:old OR ext:rar OR ext:7z OR ext:tar OR ext:gz)',
    'site:TARGET-DOMAIN.COM (ext:env OR ext:ini OR ext:cfg OR ext:conf OR ext:yml OR ext:yaml) -github',
    'site:TARGET-DOMAIN.COM (ext:log OR "stack trace" OR "exception in thread")',
    'site:TARGET-DOMAIN.COM ("index of" OR "parent directory")',
    'site:TARGET-DOMAIN.COM (inurl:.git OR inurl:.svn OR inurl:.hg)',
    'site:TARGET-DOMAIN.COM (inurl:swagger OR inurl:openapi) (ext:json OR ext:yaml OR ext:yml)',
    'site:TARGET-DOMAIN.COM (inurl:graphql OR "IntrospectionQuery")',
    'site:TARGET-DOMAIN.COM ext:json ("api_key" OR "apikey" OR "token" OR "secret")',
    'site:TARGET-DOMAIN.COM (ext:txt OR ext:pdf OR ext:doc OR ext:docx) ("password" OR "PRIVATE KEY")',
    'site:TARGET-DOMAIN.COM (inurl:robots.txt OR inurl:sitemap.xml)',
    'site:github.com "TARGET-DOMAIN.COM" (".env" OR "PRIVATE KEY")',
    'site:gitlab.com "TARGET-DOMAIN.COM" ("token" OR "apikey" OR "password")',
    'site:pastebin.com "TARGET-DOMAIN.COM"',
    'site:trello.com "TARGET-DOMAIN.COM"',
    'site:TARGET-DOMAIN.COM (inurl:redirect= OR inurl:return= OR inurl:url= OR inurl:next=) inurl:http',
    'site:TARGET-DOMAIN.COM (inurl:dev OR inurl:staging OR inurl:test OR inurl:temp) -inurl:docs',
    'site:s3.amazonaws.com "TARGET-DOMAIN.COM"',
    'site:blob.core.windows.net "TARGET-DOMAIN.COM"',
    'site:googleapis.com "TARGET-DOMAIN.COM"',
    'site:storage.googleapis.com "TARGET-DOMAIN.COM"',
    'site:amazonaws.com intext:"TARGET-DOMAIN.COM"',
    'site:firebasestorage.googleapis.com "TARGET-DOMAIN.COM"',
    'site:*.TARGET-DOMAIN.COM (ext:doc OR ext:pdf OR ext:xls OR ext:json OR ext:zip OR ext:sql OR ext:bak OR ext:conf)',
)

_DOMAIN_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$", re.I)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _dork_catalog_path() -> Path:
    env = (os.environ.get("FIREBREAK_DORK_CATALOG") or "").strip()
    if env:
        return Path(env)
    return _repo_root() / "340k.txt"


@lru_cache(maxsize=1)
def load_dork_catalog(*, limit: int | None = None) -> tuple[str, ...]:
    """Load extended dork lines from 340k.txt (cached)."""
    path = _dork_catalog_path()
    if not path.is_file():
        return CORE_DORKS
    rows: list[str] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                row = line.strip()
                if not row or row.startswith("#"):
                    continue
                rows.append(row)
                if limit and len(rows) >= limit:
                    break
    except OSError:
        return CORE_DORKS
    return tuple(rows) if rows else CORE_DORKS


def normalize_domain(domain: str) -> str:
    raw = (domain or "").strip().lower()
    raw = raw.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
    if not raw or not _DOMAIN_RE.match(raw):
        raise ValueError("invalid domain for dork substitution")
    return raw


def substitute_domain(template: str, domain: str) -> str:
    d = normalize_domain(domain)
    return template.replace(TARGET_TOKEN, d).replace("target-domain.com", d)


def dorks_for_domain(domain: str, *, include_catalog: bool = True, catalog_limit: int = 200) -> list[str]:
    """Return ready-to-run dork queries for an authorized domain."""
    templates = list(CORE_DORKS)
    if include_catalog:
        templates.extend(load_dork_catalog(limit=catalog_limit))
    seen: set[str] = set()
    out: list[str] = []
    for template in templates:
        if TARGET_TOKEN not in template and "target-domain" not in template.lower():
            continue
        query = substitute_domain(template, domain)
        if query not in seen:
            seen.add(query)
            out.append(query)
    return out


def sample_dorks(domain: str, *, count: int = 12) -> list[str]:
    return dorks_for_domain(domain, include_catalog=False)[:count]
