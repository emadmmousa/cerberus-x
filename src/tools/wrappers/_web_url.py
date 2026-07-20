"""Canonicalize scan targets to HTTPS URLs that avoid ISP HTTP hijacks."""

from __future__ import annotations

import ssl
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def ensure_https_url(target: str) -> str:
    """Return an absolute HTTPS URL for a host or URL target."""
    value = (target or "").strip()
    if not value:
        raise ValueError("target is required")
    if "://" not in value:
        value = f"https://{value}"
    parsed = urlparse(value)
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"invalid target: {target}")
    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"https://{netloc}{path}{query}{fragment}".rstrip("/") or f"https://{netloc}"


def _https_upgrade_location(location: str, fallback_host: str) -> Optional[str]:
    if not location:
        return None
    if "://" not in location:
        location = f"https://{fallback_host.rstrip('/')}/{location.lstrip('/')}"
    parsed = urlparse(location)
    host = parsed.hostname
    if not host:
        return None
    netloc = host
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"https://{netloc}{path}{query}".rstrip("/") or f"https://{netloc}"


def _probe_redirect(url: str, timeout: float = 8.0) -> Optional[str]:
    """Return Location for a redirect without following it (avoids ISP HTTP portals)."""
    ctx = ssl.create_default_context()
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=ctx))
    for method in ("HEAD", "GET"):
        req = Request(url, method=method, headers={"User-Agent": "cerberus-x/1.0"})
        try:
            with opener.open(req, timeout=timeout) as resp:
                # No redirect (or already at final HTTPS page).
                code = getattr(resp, "status", None) or resp.getcode()
                if code in {301, 302, 303, 307, 308}:
                    return resp.headers.get("Location")
                return None
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                return exc.headers.get("Location")
            if method == "HEAD" and exc.code in {405, 501}:
                continue
            return None
        except (URLError, TimeoutError, OSError, ValueError):
            if method == "HEAD":
                continue
            return None
    return None


def force_url_arg(
    args: list[str],
    url: str,
    *,
    flags: tuple[str, ...] = ("-u", "--url"),
    with_fuzz: bool = False,
) -> list[str]:
    """Replace any existing URL flag value with the canonical HTTPS URL."""
    final_url = f"{url.rstrip('/')}/FUZZ" if with_fuzz else url
    out: list[str] = []
    skip_next = False
    seen = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in flags and index + 1 < len(args):
            out.extend([arg, final_url])
            skip_next = True
            seen = True
            continue
        # Handle -u=https://... style
        replaced = False
        for flag in flags:
            prefix = f"{flag}="
            if isinstance(arg, str) and arg.startswith(prefix):
                out.append(f"{prefix}{final_url}")
                seen = True
                replaced = True
                break
        if replaced:
            continue
        out.append(arg)
    if not seen:
        out.extend([flags[0], final_url])
    return out


def canonicalize_web_url(target: str, *, probe: bool = True) -> str:
    """
    Force HTTPS and, when the apex redirects to www over HTTP, prefer https://www.

    Plain HTTP is unsafe from many residential/ISP networks that inject captive
    portals (e.g. TEDATA megaplusredirection). Never return an http:// URL.
    """
    url = ensure_https_url(target)
    if not probe:
        return url

    parsed = urlparse(url)
    host = parsed.hostname or ""
    location = _probe_redirect(url)
    if not location:
        return url

    upgraded = _https_upgrade_location(location, host)
    if not upgraded:
        return url

    loc_host = (urlparse(upgraded).hostname or "").lower()
    if loc_host.startswith("www.") and not host.lower().startswith("www."):
        # Apex → www downgrade (http://www) is common; stay on HTTPS www.
        path = parsed.path if parsed.path and parsed.path != "/" else ""
        query = f"?{parsed.query}" if parsed.query else ""
        return f"https://{loc_host}{path}{query}".rstrip("/") or f"https://{loc_host}"

    # Same host HTTP downgrade → keep HTTPS on current host.
    return url
