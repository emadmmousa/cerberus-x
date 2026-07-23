import os
import re
import subprocess

from tools.osint_scrape import parse_seeds, pick_web_url, skip_result, strip_osint_seed_args
from tools.waf_evasion import build_evasion_headers, random_delay
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_WHATWEB_TIMEOUT", "120"))
_DEFAULT_OPEN_TIMEOUT = int(os.environ.get("FIREBREAK_WHATWEB_OPEN_TIMEOUT", "20"))
_DEFAULT_READ_TIMEOUT = int(os.environ.get("FIREBREAK_WHATWEB_READ_TIMEOUT", "60"))
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_TECH_RE = re.compile(r"([A-Za-z][A-Za-z0-9_.-]*(?:\s[A-Za-z0-9_.-]+)?)\[[^\]]*\]")
_EXPIRED_RE = re.compile(r"execution expired|ERROR Opening", re.IGNORECASE)
_SKIP_TECH_NAMES = frozenset(
    {
        "country",
        "ip",
        "email",
        "uncommonheaders",
        "open-graph-protocol",
        "http",
        "https",
        "error",
        "cookies",
        "httponly",
        "title",
        "script",
        "x-frame-options",
        "x-ua-compatible",
    }
)
_VALUE_TECH_NAMES = frozenset({"x-powered-by", "httpserver"})
_CATEGORY_ONLY = frozenset({"cloudflare", "html5"})
_CHALLENGE_TITLE_RE = re.compile(r"just a moment|attention required|checking your browser", re.I)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _url(target: str) -> str:
    return canonicalize_web_url(target)


def _has_flag(args: list[str], flag: str) -> bool:
    return flag in args or any(str(a).startswith(f"{flag}=") for a in args)


def _ensure_flag(args: list[str], flag: str, value: str) -> list[str]:
    if _has_flag(args, flag):
        return args
    return [*args, flag, value]


def _aggression(args: list[str]) -> int | None:
    for index, arg in enumerate(args):
        if arg == "-a" and index + 1 < len(args):
            try:
                return int(str(args[index + 1]))
            except ValueError:
                return None
        if str(arg).startswith("-a="):
            try:
                return int(str(arg).split("=", 1)[1])
            except ValueError:
                return None
    return None


def _set_aggression(args: list[str], level: int) -> list[str]:
    out: list[str] = []
    skip = False
    for index, arg in enumerate(args):
        if skip:
            skip = False
            continue
        if arg == "-a" and index + 1 < len(args):
            out.extend(["-a", str(level)])
            skip = True
            continue
        if str(arg).startswith("-a="):
            out.append(f"-a={level}")
            continue
        out.append(arg)
    if _aggression(out) is None:
        out = ["-a", str(level), *out]
    return out


def _normalize_args(args: list[str] | None, evasion=None) -> list[str]:
    evasion = evasion or {}
    normalized = list(args or ["-a", "2"])
    normalized = _ensure_flag(normalized, "--open-timeout", str(_DEFAULT_OPEN_TIMEOUT))
    normalized = _ensure_flag(normalized, "--read-timeout", str(_DEFAULT_READ_TIMEOUT))
    stealthy = bool(
        evasion.get("random_headers")
        or evasion.get("rotate_user_agent")
        or float(evasion.get("random_delay_min") or 0) > 0
    )
    if stealthy:
        normalized = _set_aggression(normalized, min(_aggression(normalized) or 3, 1))
        normalized = _ensure_flag(normalized, "--max-threads", "1")
        normalized = _ensure_flag(normalized, "--open-timeout", "25")
        normalized = _ensure_flag(normalized, "--read-timeout", "90")
    if evasion.get("random_headers", False):
        headers = build_evasion_headers(evasion)
        ua = headers.get("User-Agent") or headers.get("user-agent")
        if ua and not _has_flag(normalized, "--user-agent"):
            normalized = _ensure_flag(normalized, "--user-agent", str(ua))
    return normalized


def _parse_http_status(output: str) -> str | None:
    clean = _strip_ansi(output)
    match = re.search(r"\[(\d{3}\s+[^\]]+)\]", clean)
    return match.group(1).strip() if match else None


def _normalize_tech_name(name: str) -> str:
    token = (name or "").strip()
    if not token:
        return ""
    low = token.lower()
    if low in {"cloudflare", "cloud flare"}:
        return "Cloudflare"
    if low == "html5":
        return "HTML5"
    return token


def _parse_page_title(output: str) -> str | None:
    clean = _strip_ansi(output)
    match = re.search(r"Title\[([^\]]+)\]", clean, re.I)
    if not match:
        return None
    title = match.group(1).strip()
    return title or None


def _detect_waf_challenge(output: str, http_status: str | None) -> dict[str, object]:
    clean = _strip_ansi(output)
    title = _parse_page_title(output) or ""
    status_code = None
    if http_status:
        code_match = re.match(r"(\d{3})", http_status)
        if code_match:
            status_code = int(code_match.group(1))
    indicators = [
        "cf-mitigated" in clean.lower(),
        "__cf_bm" in clean.lower(),
        "cloudflare" in clean.lower() and status_code in {403, 503, 429},
        bool(_CHALLENGE_TITLE_RE.search(title)),
        bool(_CHALLENGE_TITLE_RE.search(clean)),
    ]
    blocked = sum(1 for flag in indicators if flag) >= 2 or (
        status_code == 403 and "cloudflare" in clean.lower()
    )
    vendor = "Cloudflare" if "cloudflare" in clean.lower() or "__cf_bm" in clean.lower() else None
    return {
        "waf_blocked": bool(blocked),
        "waf_vendor": vendor,
        "page_title": title or None,
        "http_status_code": status_code,
    }


def _parse_technologies(output: str) -> list[str]:
    clean = _strip_ansi(output)
    seen: set[str] = set()
    techs: list[str] = []

    def _add(name: str) -> None:
        token = _normalize_tech_name(name)
        if not token:
            return
        key = token.lower()
        if key in seen or key in _SKIP_TECH_NAMES:
            return
        if key in _CATEGORY_ONLY and key in seen:
            return
        seen.add(key)
        techs.append(token)

    for line in clean.splitlines():
        if "http" not in line.lower():
            continue
        status_end = re.search(r"\[\d{3}[^\]]*\]", line)
        if not status_end:
            continue
        payload = line[status_end.end() :].strip()
        if not payload:
            continue

        bracket_spans: list[tuple[int, int]] = []
        for match in re.finditer(r"([A-Za-z][A-Za-z0-9_. -]*?)\[([^\]]*)\]", payload):
            name, value = match.group(1).strip(), match.group(2).strip()
            lname = name.lower()
            bracket_spans.append((match.start(), match.end()))
            if lname in _SKIP_TECH_NAMES:
                continue
            if lname in _VALUE_TECH_NAMES and value:
                _add(value.split(",")[0].strip())
            elif lname not in _SKIP_TECH_NAMES:
                _add(name)

        plain_payload = payload
        for start, end in reversed(bracket_spans):
            plain_payload = plain_payload[:start] + plain_payload[end:]
        for part in plain_payload.split(","):
            part = part.strip()
            if not part:
                continue
            plain = re.match(r"^([A-Za-z][A-Za-z0-9_.-]+)$", part)
            if plain:
                _add(plain.group(1))

    return techs


def _looks_expired(output: str) -> bool:
    return bool(_EXPIRED_RE.search(output or ""))


def _run_once(
    url: str,
    args: list[str],
    resolved: dict,
    env: dict,
    timeout: int,
) -> tuple[str, int]:
    cmd = ["whatweb", *args, *resolved["flags"], url]
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        start_new_session=True,
        check=False,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    return output, completed.returncode


def scan(
    target,
    args=None,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion=None,
    timeout: int | None = None,
):
    if evasion is None:
        evasion = {}
    seeds = parse_seeds(target, args)
    web_url = pick_web_url(target, seeds)
    if not web_url:
        return skip_result(
            "whatweb",
            target,
            seeds=seeds,
            note="Web fingerprint scraping requires a domain, URL, or social profile seed.",
        )
    url = _url(web_url)
    wall_timeout = timeout or DEFAULT_TIMEOUT_SECONDS
    resolved, meta = proxy_meta("whatweb", use_proxy, proxy_protocol)
    env = merge_env(resolved["env"])
    normalized = _normalize_args(strip_osint_seed_args(list(args) if args else None), evasion)

    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )

    try:
        output, returncode = _run_once(url, normalized, resolved, env, wall_timeout)
        if _looks_expired(output) and (_aggression(normalized) or 3) > 1:
            retry_args = _normalize_args(["-a", "1"], evasion)
            retry_args = _ensure_flag(retry_args, "--open-timeout", "30")
            retry_args = _ensure_flag(retry_args, "--read-timeout", "120")
            retry_out, retry_code = _run_once(
                url, retry_args, resolved, env, wall_timeout
            )
            if retry_out.strip():
                output = retry_out
                returncode = retry_code

        technologies = _parse_technologies(output)
        status = _parse_http_status(output)
        waf = _detect_waf_challenge(output, status)
        payload = {
            "tool": "whatweb",
            "target": url,
            "raw_output": output,
            "technologies": technologies,
            "proxy": meta,
        }
        if status:
            payload["http_status"] = status
        if waf.get("page_title"):
            payload["page_title"] = waf["page_title"]
        if waf.get("waf_blocked"):
            payload["waf_blocked"] = True
            payload["partial"] = True
            payload["waf_vendor"] = waf.get("waf_vendor")
            payload["note"] = (
                f"{waf.get('waf_vendor') or 'WAF'} challenge page detected "
                f"({status or 'blocked'}) — app fingerprint limited; enable proxy/evasion for deeper scans."
            )
        elif technologies:
            payload["status_line"] = technologies[0]

        expired = _looks_expired(output)
        if expired and not technologies:
            payload["error"] = "whatweb timed out before fingerprinting completed"
            payload["partial"] = True
        elif expired and technologies:
            payload["partial"] = True
            payload["note"] = "whatweb hit a read timeout but captured partial fingerprint data"
        elif returncode != 0 and not output.strip():
            payload["error"] = f"whatweb exited with code {returncode}"
        elif returncode != 0 and _looks_expired(output):
            payload["partial"] = True
            payload["error"] = "whatweb timed out before fingerprinting completed"
        return payload
    except FileNotFoundError:
        return {
            "tool": "whatweb",
            "target": url,
            "error": "whatweb binary not found",
            "proxy": meta,
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        technologies = _parse_technologies(output)
        return {
            "tool": "whatweb",
            "target": url,
            "raw_output": output or f"ERROR Opening: {url} - execution expired",
            "technologies": technologies,
            "partial": True,
            "error": f"whatweb timed out after {wall_timeout}s",
            "proxy": meta,
        }
