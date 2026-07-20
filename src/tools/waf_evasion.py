"""
WAF evasion utilities for Cerberus-X.
Provides randomized headers, payload obfuscation, timing jitter, and WAF fingerprinting.
"""

from __future__ import annotations

import random
import time
from typing import Dict, List, Optional

# ----------------------------------------------------------------------
# User-Agent rotation pool
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

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.7",
    "es-ES,es;q=0.9,en;q=0.8",
    "ja-JP,ja;q=0.9,en;q=0.7",
    "zh-CN,zh;q=0.9,en;q=0.8",
]

# ----------------------------------------------------------------------
# Payload obfuscation helpers


def obfuscate_sql(payload: str) -> str:
    """Apply simple SQL obfuscation (comment insertion, case randomization)."""
    techniques = [
        lambda p: p.replace(" ", "/**/"),
        lambda p: "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(p)),
        lambda p: p.replace("OR", "||").replace("AND", "&&"),
        lambda p: p.replace("=", " LIKE "),
    ]
    return random.choice(techniques)(payload)


def obfuscate_xss(payload: str) -> str:
    """Apply simple XSS obfuscation (entity encoding, case mix)."""
    techniques = [
        lambda p: p.replace("<", "&lt;").replace(">", "&gt;"),
        lambda p: "".join(f"&#{ord(c)};" if c.isalpha() else c for c in p),
        lambda p: p.replace("script", "ScrIpT").replace("alert", "aLert"),
        lambda p: p.replace(" ", "%20").replace("=", "%3D"),
    ]
    return random.choice(techniques)(payload)


def obfuscate_rce(payload: str) -> str:
    """Apply simple RCE obfuscation (variable expansion, quoting)."""
    techniques = [
        lambda p: p.replace(" ", "${IFS}"),
        lambda p: "'" + "'".join(p) + "'",
        lambda p: p.replace("/", "${HOME:0:1}"),
        lambda p: "".join(f"\\{c}" if c.isalpha() else c for c in p),
    ]
    return random.choice(techniques)(payload)


def obfuscate_payload(payload: str, payload_type: str = "sql") -> str:
    """Dispatch to the appropriate obfuscator."""
    mapping = {
        "sql": obfuscate_sql,
        "xss": obfuscate_xss,
        "rce": obfuscate_rce,
    }
    fn = mapping.get(payload_type.lower(), obfuscate_sql)
    try:
        return fn(payload)
    except Exception:
        return payload


# ----------------------------------------------------------------------
# Header randomization


def random_headers(extra: Optional[Dict] = None) -> Dict:
    """Generate a randomized header set safe for tool wrappers."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": random.choice(
            [
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "application/json,text/plain,*/*",
                "text/plain,*/*;q=0.9",
            ]
        ),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        # Avoid brotli-only / hop-by-hop headers that break CLI HTTP clients.
        "Accept-Encoding": random.choice(["gzip, deflate", "gzip"]),
        "Cache-Control": random.choice(["no-cache", "max-age=0"]),
        "Upgrade-Insecure-Requests": random.choice(["1", "0"]),
    }
    if extra:
        headers.update(extra)
    # Never inject hop-by-hop headers into scanner tools.
    headers.pop("Connection", None)
    headers.pop("Proxy-Connection", None)
    headers.pop("Transfer-Encoding", None)
    return headers


# ----------------------------------------------------------------------
# Timing jitter


def random_delay(min_sec: float = 0.1, max_sec: float = 1.5) -> None:
    """Sleep for a random duration between min and max seconds."""
    time.sleep(random.uniform(min_sec, max_sec))


# ----------------------------------------------------------------------
# WAF detection (using wafw00f if installed)


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


# ----------------------------------------------------------------------
# Evasion profile builder


def evasion_profile(
    level: str = "medium", target_waf: Optional[str] = None
) -> Dict:
    """
    Return a dict of evasion settings based on desired aggressiveness.
    Levels: low, medium, high, aggressive
    """
    profiles = {
        "low": {
            "random_headers": True,
            "random_delay_min": 0.0,
            "random_delay_max": 0.3,
            "obfuscate_payloads": False,
            "rotate_user_agent": True,
            "use_random_proxy": False,
            "max_retries": 2,
        },
        "medium": {
            "random_headers": True,
            "random_delay_min": 0.2,
            "random_delay_max": 1.0,
            "obfuscate_payloads": True,
            "rotate_user_agent": True,
            "use_random_proxy": False,
            "max_retries": 3,
        },
        "high": {
            "random_headers": True,
            "random_delay_min": 0.5,
            "random_delay_max": 2.5,
            "obfuscate_payloads": True,
            "rotate_user_agent": True,
            "use_random_proxy": True,
            "max_retries": 5,
        },
        "aggressive": {
            "random_headers": True,
            "random_delay_min": 1.0,
            "random_delay_max": 4.0,
            "obfuscate_payloads": True,
            "rotate_user_agent": True,
            "use_random_proxy": False,
            "max_retries": 8,
        },
    }
    profile = dict(profiles.get(level.lower(), profiles["medium"]))
    profile["payload_type"] = "sql"
    if target_waf and "cloudflare" in target_waf.lower():
        profile["random_delay_min"] = max(profile["random_delay_min"], 1.0)
        profile["random_delay_max"] = max(profile["random_delay_max"], 3.0)
    return profile
