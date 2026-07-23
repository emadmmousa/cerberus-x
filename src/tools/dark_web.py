"""
Dark web OSINT methods for authorized engagements.

Searches public dark-web indexes (Ahmia, etc.), correlates leak mentions,
and probes .onion hidden services via optional Tor SOCKS. Does not access
illicit marketplaces or facilitate crime — intel gathering on in-scope targets only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from orchestrator.osint.breach_service import seeds_from_target_and_args
from orchestrator.osint.seeds import normalize_osint_seeds

_ONION_RE = re.compile(r"\b[a-z2-7]{16,56}\.onion\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")

# Public clearnet gateways / indexes (no Tor required for search HTML).
_SEARCH_ENGINES: tuple[tuple[str, str], ...] = (
    ("ahmia", "https://ahmia.fi/search/?q={query}"),
    ("torch_mirror", "https://torchdeedp3i2jigzjdmfpn5ttjhthh5wbmda2rr3jvqjg5p7c54dqd.onion/search?query={query}"),
)

DEFAULT_METHODS: tuple[str, ...] = (
    "onion_search",
    "mention_scan",
    "leak_hunt",
    "paste_monitor",
    "breach_correlate",
    "market_mention",
    "forum_mention",
    "onion_probe",
    "tor_fingerprint",
)


def tor_socks_url() -> str | None:
    raw = (os.environ.get("FIREBREAK_TOR_SOCKS") or os.environ.get("TOR_SOCKS") or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"socks5h://{raw}"
    return raw


def dark_web_enabled() -> bool:
    return os.environ.get("FIREBREAK_DARKWEB_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _domain(target: str) -> str:
    value = (target or "").strip()
    if value.lower().endswith(".onion"):
        return value.lower()
    if "://" in value:
        from urllib.parse import urlparse

        host = urlparse(value).hostname or value
        return host.split("/")[0].split(":")[0].lower()
    return value.split("/")[0].split(":")[0].lower()


def _brand(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) >= 2 and parts[0] not in {"www", "mail", "api", "app"}:
        return parts[0]
    return parts[0] if parts else domain


def list_dark_web_methods() -> dict[str, list[str]]:
    """Operator-facing inventory of implemented dark-web method families."""
    return {
        "discovery": [
            "onion_search",
            "mention_scan",
            "onion_probe",
        ],
        "leak_intel": [
            "leak_hunt",
            "paste_monitor",
            "breach_correlate",
            "email_exposure",
        ],
        "underground_mentions": [
            "forum_mention",
            "market_mention",
            "credential_dump_search",
        ],
        "hidden_service": [
            "tor_fingerprint",
            "onion_header_probe",
            "onion_path_probe",
        ],
        "aggregate": ["full"],
        "requires_tor": [
            "onion_probe",
            "tor_fingerprint",
            "onion_header_probe",
            "onion_path_probe",
        ],
        "clearnet_only": [
            "onion_search",
            "mention_scan",
            "leak_hunt",
            "paste_monitor",
            "breach_correlate",
            "forum_mention",
            "market_mention",
        ],
    }


def _http_get(url: str, *, timeout: int = 25, via_tor: bool = False) -> tuple[int, str]:
    socks = tor_socks_url() if via_tor else None
    if socks and via_tor:
        return _curl_fetch(url, socks=socks, timeout=timeout)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Firebreak-OSINT/1.0 (+authorized-engagement)",
            "Accept": "text/html,application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except Exception as exc:
        return 0, str(exc)


def _curl_fetch(url: str, *, socks: str, timeout: int = 30) -> tuple[int, str]:
    proxy = socks.replace("socks5h://", "").replace("socks5://", "")
    cmd = [
        "curl",
        "-sS",
        "-m",
        str(timeout),
        "--proxy",
        f"socks5h://{proxy}",
        "-A",
        "Firebreak-OSINT/1.0",
        "-w",
        "\n__HTTP_CODE__:%{http_code}",
        url,
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return 0, "curl not installed"
    except subprocess.CalledProcessError as exc:
        out = exc.output or str(exc)
    code = 0
    if "__HTTP_CODE__:" in out:
        body, _, tail = out.rpartition("\n__HTTP_CODE__:")
        try:
            code = int(tail.strip())
        except ValueError:
            code = 0
        return code, body
    return code, out


def _search_queries(domain: str) -> dict[str, list[str]]:
    brand = _brand(domain)
    return {
        "onion_search": [
            domain,
            brand,
            f'"{domain}" onion',
            f"{brand} hidden service",
        ],
        "mention_scan": [
            f'"{domain}"',
            f'"{brand}" hack',
            f'"{domain}" breach',
        ],
        "leak_hunt": [
            f'"{domain}" password',
            f'"{domain}" leak',
            f'"{domain}" dump',
            f'"{brand}" credentials',
        ],
        "paste_monitor": [
            f'"{domain}" paste',
            f'"{domain}" pastebin',
            f'"{brand}" leak site',
        ],
        "breach_correlate": [
            f'"{domain}" database',
            f'"{domain}" combo list',
            f'"{domain}" stolen',
        ],
        "forum_mention": [
            f'"{domain}" forum',
            f'"{brand}" exploit forum',
        ],
        "market_mention": [
            f'"{domain}" market',
            f'"{brand}" sale',
        ],
        "credential_dump_search": [
            f'"{domain}" "@{domain}"',
            f'"{domain}" sql dump',
        ],
        "email_exposure": [
            f'"@{domain}"',
            f'"{domain}" email leak',
        ],
    }


def _extract_onions(text: str) -> list[str]:
    found = {m.lower() for m in _ONION_RE.findall(text or "")}
    return sorted(found)


def _extract_snippets(text: str, needle: str, limit: int = 8) -> list[str]:
    snippets: list[str] = []
    lower = (text or "").lower()
    needle_l = needle.lower()
    start = 0
    while len(snippets) < limit:
        idx = lower.find(needle_l, start)
        if idx < 0:
            break
        chunk = text[max(0, idx - 60) : idx + len(needle) + 80].replace("\n", " ")
        snippets.append(chunk.strip()[:200])
        start = idx + len(needle)
    return snippets


def _social_handle(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url if "://" in url else f"https://{url.lstrip('/')}")
    parts = [p for p in (parsed.path or "").split("/") if p]
    if parts:
        return parts[-1].lstrip("@")
    return (parsed.hostname or "").split(".")[0]


def _match_needles(domain: str, seeds: list[dict[str, str]] | None) -> list[str]:
    needles = [domain, _brand(domain)]
    for seed in seeds or []:
        value = str(seed.get("value") or "").strip()
        display = str(seed.get("display") or value).strip()
        for token in (value, display):
            if token and len(token) >= 2:
                needles.append(token)
        kind = str(seed.get("kind") or "")
        if kind == "social_url":
            handle = _social_handle(value)
            if handle:
                needles.append(handle)
        elif kind == "username":
            needles.append(value.lstrip("@"))
    return list(dict.fromkeys(n for n in needles if n))


def _search_queries_for_context(
    domain: str,
    method: str,
    seeds: list[dict[str, str]] | None,
) -> list[str]:
    queries = list(_search_queries(domain).get(method, [domain]))
    if not seeds:
        return queries[:8]
    extra: list[str] = []
    for seed in seeds:
        kind = str(seed.get("kind") or "")
        value = str(seed.get("value") or "").strip()
        if not value:
            continue
        if kind == "email":
            extra.extend([f'"{value}"', f'"{value}" leak', f'"{value}" password'])
        elif kind in {"username", "social_url"}:
            handle = value.lstrip("@") if kind == "username" else _social_handle(value)
            if handle:
                extra.extend([f'"{handle}"', f'"{handle}" leak', f'"{handle}" credentials'])
        elif kind == "mobile":
            extra.extend([f'"{value}"', f'"{value}" leak'])
        elif kind == "full_name":
            extra.extend([f'"{value}"', f'"{value}" leak'])
        elif kind == "domain":
            extra.extend(_search_queries(_domain(value)).get(method, [value]))
    merged = list(dict.fromkeys([*extra, *queries]))
    return merged[:8]


def _body_matches_needles(
    body: str,
    needles: list[str],
    seeds: list[dict[str, str]] | None = None,
) -> bool:
    lower = (body or "").lower()
    domain_needles = needles[:2]
    if any(needle.lower() in lower for needle in domain_needles if needle):
        return True
    extra_seeds = seeds or []
    has_explicit_seeds = any(
        str(seed.get("kind") or "") not in {"", "domain"} for seed in extra_seeds
    ) or len(extra_seeds) > 1
    if not has_explicit_seeds:
        return bool(_ONION_RE.search(body or ""))
    for needle in needles[2:]:
        if needle and needle.lower() in lower:
            return True
    return False


def _run_index_searches(
    method: str,
    domain: str,
    *,
    seeds: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    queries = _search_queries_for_context(domain, method, seeds)
    needles = _match_needles(domain, seeds)
    onions: set[str] = set()
    hits: list[dict[str, Any]] = []
    errors: list[str] = []

    for q in queries[:4]:
        for engine, template in _SEARCH_ENGINES[:1]:  # Ahmia clearnet (reliable)
            url = template.format(query=urllib.parse.quote(q))
            status, body = _http_get(url, via_tor=False)
            if status == 0:
                errors.append(f"{engine}:{q[:40]}: {body[:120]}")
                continue
            if not _body_matches_needles(body, needles, seeds):
                continue
            found = _extract_onions(body)
            onions.update(found)
            snippets: list[str] = []
            for needle in needles:
                snippets.extend(_extract_snippets(body, needle))
            snippets = list(dict.fromkeys(snippets))[:5]
            if found or snippets:
                hits.append(
                    {
                        "engine": engine,
                        "query": q,
                        "status": status,
                        "onions": found[:10],
                        "snippets": snippets,
                        "mentions": len(snippets),
                    }
                )

    return {
        "method": method,
        "queries": queries[:4],
        "needles": needles[:8],
        "onions": sorted(onions),
        "hits": hits,
        "errors": errors,
        "productive": bool(onions or hits),
    }


def _probe_onion(onion_url: str) -> dict[str, Any]:
    url = onion_url if onion_url.startswith("http") else f"http://{onion_url}"
    socks = tor_socks_url()
    if not socks:
        return {
            "method": "onion_probe",
            "url": url,
            "error": "Tor SOCKS not configured (set FIREBREAK_TOR_SOCKS)",
            "skipped": True,
        }
    status, body = _curl_fetch(url, socks=socks, timeout=45)
    title = ""
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    return {
        "method": "onion_probe",
        "url": url,
        "status": status,
        "title": title,
        "headers_sample": body[:400] if status else body[:200],
        "productive": status in (200, 301, 302, 401, 403),
    }


def _tor_fingerprint(onion_url: str) -> dict[str, Any]:
    url = onion_url if onion_url.startswith("http") else f"http://{onion_url}"
    socks = tor_socks_url()
    if not socks:
        return {
            "method": "tor_fingerprint",
            "url": url,
            "error": "Tor SOCKS not configured",
            "skipped": True,
        }
    proxy = socks.replace("socks5h://", "").replace("socks5://", "")
    cmd = [
        "curl",
        "-sS",
        "-I",
        "-m",
        "40",
        "--proxy",
        f"socks5h://{proxy}",
        url,
    ]
    try:
        headers = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except Exception as exc:
        return {"method": "tor_fingerprint", "url": url, "error": str(exc)[:200]}
    return {
        "method": "tor_fingerprint",
        "url": url,
        "headers": headers[:1200],
        "productive": "HTTP/" in headers,
    }


def run_dark_web_method(
    method: str,
    target: str,
    *,
    seeds: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute one dark-web OSINT method against authorized seeds (scrape/index only)."""
    domain = _domain(target)
    method = (method or "full").strip().lower().replace("-", "_")
    context_seeds = normalize_osint_seeds(seeds) if seeds else None

    if method == "full":
        results = []
        for name in DEFAULT_METHODS:
            if name in {"onion_probe", "tor_fingerprint"}:
                continue
            results.append(run_dark_web_method(name, target, seeds=context_seeds))
        onions: set[str] = set()
        for row in results:
            onions.update(row.get("onions") or [])
        if domain.endswith(".onion"):
            onions.add(domain)
        probe_rows = []
        for onion in sorted(onions)[:3]:
            probe_rows.append(_probe_onion(onion))
            probe_rows.append(_tor_fingerprint(onion))
        return {
            "method": "full",
            "target": domain,
            "sub_results": results,
            "onion_probes": probe_rows,
            "onions": sorted(onions),
            "productive": any(r.get("productive") for r in results)
            or any(r.get("productive") for r in probe_rows),
        }

    if domain.endswith(".onion"):
        if method in {"onion_probe", "onion_header_probe"}:
            return _probe_onion(domain)
        if method in {"tor_fingerprint", "onion_path_probe"}:
            return _tor_fingerprint(domain)

    if method in {
        "onion_search",
        "mention_scan",
        "leak_hunt",
        "paste_monitor",
        "breach_correlate",
        "forum_mention",
        "market_mention",
        "credential_dump_search",
        "email_exposure",
    }:
        row = _run_index_searches(method, domain, seeds=context_seeds)
        row["target"] = domain
        return row

    if method == "onion_probe":
        search = _run_index_searches("onion_search", domain, seeds=context_seeds)
        onions = search.get("onions") or []
        if not onions:
            return {
                "method": method,
                "target": domain,
                "onions": [],
                "note": "No .onion URLs discovered to probe",
                "productive": False,
            }
        probes = [_probe_onion(o) for o in onions[:3]]
        return {
            "method": method,
            "target": domain,
            "onions": onions,
            "probes": probes,
            "productive": any(p.get("productive") for p in probes),
        }

    if method == "tor_fingerprint":
        search = _run_index_searches("onion_search", domain)
        onions = search.get("onions") or []
        if domain.endswith(".onion"):
            onions = [domain]
        if not onions:
            return {
                "method": method,
                "target": domain,
                "note": "No .onion URLs to fingerprint",
                "productive": False,
            }
        fps = [_tor_fingerprint(o) for o in onions[:2]]
        return {
            "method": method,
            "target": domain,
            "fingerprints": fps,
            "productive": any(f.get("productive") for f in fps),
        }

    return {
        "method": method,
        "target": domain,
        "error": f"Unknown dark-web method: {method}",
        "available": list_dark_web_methods(),
    }


def parse_osint_seeds_args(target: str, args: list[str] | None) -> list[dict[str, str]]:
    return seeds_from_target_and_args(target, args)


def parse_method_args(args: list[str] | None) -> str:
    """Parse --method NAME from argv; default full."""
    argv = list(args or [])
    if "--method" in argv:
        idx = argv.index("--method")
        if idx + 1 < len(argv):
            return str(argv[idx + 1]).strip().lower()
    for token in argv:
        if token.startswith("--method="):
            return token.split("=", 1)[1].strip().lower()
    if argv and not argv[0].startswith("-"):
        return argv[0].strip().lower()
    return "full"
