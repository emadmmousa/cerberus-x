import os
import re
import subprocess

from tools.waf_evasion import build_evasion_headers, random_delay
from tools.wrappers._argv import coerce_argv
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._wordlists import DEFAULT_WORDLIST, WORDLIST_ALIASES, resolve_wordlist
from tools.wrappers._web_url import canonicalize_web_url, force_url_arg

WORDLIST = DEFAULT_WORDLIST
QUICK_WORDLIST = "/usr/share/dirb/wordlists/small.txt"
_MAXTIME_RE = re.compile(r"maximum running time", re.IGNORECASE)
_PROGRESS_RE = re.compile(
    r"Progress:\s*\[(?P<done>\d+)/(?P<total>\d+)\].*?Errors:\s*(?P<errors>\d+)",
    re.IGNORECASE,
)
_WORDLIST_ALIASES = {
    **WORDLIST_ALIASES,
    "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt": WORDLIST,
}
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
_RESULT_RE = re.compile(
    r"^(?P<path>.*?)\s*\[Status:\s*(?P<status>\d+)(?:,\s*Size:\s*(?P<size>\d+))?.*?\]",
    re.IGNORECASE,
)


def _url(target: str) -> str:
    return canonicalize_web_url(target).rstrip("/")


def _maxtime_ceiling() -> int:
    raw = (os.environ.get("FIREBREAK_FFUF_MAXTIME") or "300").strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return 300


def _flag_value(args: list[str], flag: str, default: int) -> int:
    for index, arg in enumerate(args):
        if arg == flag and index + 1 < len(args):
            try:
                return max(1, int(str(args[index + 1]).strip()))
            except ValueError:
                return default
        prefix = f"{flag}="
        if isinstance(arg, str) and arg.startswith(prefix):
            try:
                return max(1, int(arg.split("=", 1)[1].strip()))
            except ValueError:
                return default
    return default


def _wordlist_from_args(args: list[str]) -> str | None:
    for index, arg in enumerate(args):
        if arg in {"-w", "--wordlist"} and index + 1 < len(args):
            return str(args[index + 1]).strip()
        if isinstance(arg, str) and arg.startswith(("-w=", "--wordlist=")):
            return arg.split("=", 1)[1].strip()
    return None


def _count_wordlist_lines(path: str | None) -> int:
    if not path or not os.path.isfile(path):
        return 2000
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 2000


def _stealthy_evasion(evasion: dict) -> bool:
    return bool(
        evasion.get("random_headers")
        or evasion.get("rotate_user_agent")
        or float(evasion.get("random_delay_min") or 0) > 0
    )


def _compute_maxtime(args: list[str], *, rate_default: int = 15) -> int:
    """Scale ffuf wall time to wordlist size and effective throughput."""
    wordlist = _wordlist_from_args(args)
    lines = _count_wordlist_lines(wordlist)
    rate = _flag_value(args, "-rate", 0) or _flag_value(args, "--rate", 0)
    threads = _flag_value(args, "-t", 10)
    throughput = rate if rate > 0 else max(threads * 2, rate_default)
    throughput = max(throughput, 5)
    needed = int(lines / throughput) + 45
    return max(60, min(_maxtime_ceiling(), needed))


def _set_maxtime(args: list[str], seconds: int) -> list[str]:
    args = _drop_flag(args, "-maxtime", "--maxtime")
    return [*args, "-maxtime", str(max(30, seconds))]


def _prefer_quick_wordlist(args: list[str]) -> list[str]:
    """Under CDN/stealth, prefer a smaller list so bounded runs still finish."""
    try:
        quick = resolve_wordlist(QUICK_WORDLIST)
    except FileNotFoundError:
        return args
    args = _drop_flag(args, "-w", "--wordlist")
    return [*args, "-w", quick]


def _progress_stats(output: str) -> dict[str, int]:
    stats = {"done": 0, "total": 0, "errors": 0}
    for match in _PROGRESS_RE.finditer(_ANSI_RE.sub("", output or "")):
        stats["done"] = max(stats["done"], int(match.group("done")))
        stats["total"] = max(stats["total"], int(match.group("total")))
        stats["errors"] = max(stats["errors"], int(match.group("errors")))
    return stats


def _hit_maxtime(output: str) -> bool:
    return bool(_MAXTIME_RE.search(output or ""))


def _drop_flag(args: list[str], *flags: str) -> list[str]:
    """Remove flag and its value when the flag takes one."""
    value_flags = {"-t", "-rate", "-p", "-maxtime", "-w", "--wordlist", "-u", "--url"}
    out: list[str] = []
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in flags:
            if arg in value_flags and index + 1 < len(args):
                skip_next = True
            continue
        out.append(arg)
    return out


def _session_header_names() -> frozenset[str]:
    return frozenset(
        {
            "cookie",
            "authorization",
            "x-xsrf-token",
            "x-csrf-token",
            "x-requested-with",
        }
    )


def _is_session_header(value: str) -> bool:
    name = str(value or "").split(":", 1)[0].strip().lower()
    return name in _session_header_names()


def _rejoin_header_args(args: list[str]) -> list[str]:
    """Repair shlex-split header values like ``Cookie:`` + ``token=abc``."""
    out: list[str] = []
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in {"-H", "--header"} and index + 1 < len(args):
            nxt = str(args[index + 1])
            if nxt.endswith(":") and index + 2 < len(args):
                third = str(args[index + 2])
                if not third.startswith("-"):
                    out.extend([arg, f"{nxt} {third}"])
                    skip_next = True
                    continue
            out.extend([arg, nxt])
            skip_next = True
            continue
        out.append(arg)
    return out


def _cdn_backoff(args: list[str], evasion: dict) -> list[str]:
    """
    Cloudflare/CDN edges often stall ffuf at 0 req/sec when auto-calibrate
    plus random stealth headers plus high thread counts collide.
    """
    if not _stealthy_evasion(evasion):
        return args

    # Auto-calibrate with rotating headers produces unstable baselines → hang.
    args = _drop_flag(args, "-ac", "--auto-calibrate")
    args = _drop_flag(args, "-t")
    args = _drop_flag(args, "-rate")
    # Drop flood of stealth -H headers under CDN — they often trigger WAF challenges.
    stripped: list[str] = []
    skip = False
    header_count = 0
    for index, arg in enumerate(args):
        if skip:
            skip = False
            continue
        if arg in {"-H", "--header"}:
            # Keep at most one User-Agent style header if present; drop IP spoof noise.
            if index + 1 < len(args):
                value = str(args[index + 1])
                skip = True
                lower = value.lower()
                if _is_session_header(value) or (
                    header_count == 0
                    and (
                        lower.startswith("user-agent:")
                        or lower.startswith("accept:")
                    )
                ):
                    stripped.extend([arg, value])
                    if not _is_session_header(value):
                        header_count += 1
            continue
        stripped.append(arg)
    args = stripped
    args = _prefer_quick_wordlist(args)
    # Slow, small bursts; wall time scales to the (smaller) wordlist.
    args.extend(["-t", "5", "-rate", "8"])
    args = _set_maxtime(args, _compute_maxtime(args, rate_default=8))
    return args


def _looks_like_cdn_stall(output: str) -> bool:
    """True only when the *final* progress line shows zero throughput + errors."""
    text = output or ""
    # Prefer the last progress line — early "0 req/sec" is normal at startup.
    progress_lines = [
        line
        for line in text.splitlines()
        if "Progress:" in line and "req/sec" in line
    ]
    if not progress_lines:
        return False
    last = _ANSI_RE.sub("", progress_lines[-1])
    if not re.search(r"::\s*0 req/sec\s*::", last):
        return False
    errors = re.search(r"Errors:\s*(\d+)", last)
    if not errors or int(errors.group(1)) < 4:
        return False
    # Require that we barely moved (stuck near start) OR hit max time with 0 rps.
    prog = re.search(r"Progress:\s*\[(\d+)/(\d+)\]", last)
    if prog:
        done, total = int(prog.group(1)), int(prog.group(2))
        if total > 0 and done / total > 0.15 and "Maximum running time" not in text:
            # Made meaningful progress earlier; final 0 rps is often end-of-run noise.
            return False
    return True


def _normalize_args(args: list[str], url: str, evasion=None) -> list[str]:
    if evasion is None:
        evasion = {}
    # Expand glued LLM tokens like "-w /tmp/w.txt http://x HTTP/1.1"
    normalized = _rejoin_header_args(
        [
            arg.replace("{{target}}", url) if isinstance(arg, str) else arg
            for arg in coerce_argv(args)
        ]
    )
    fixed: list[str] = []
    skip_next = False
    for index, arg in enumerate(normalized):
        if skip_next:
            skip_next = False
            continue
        # Drop HTTP request-line junk masquerading as flags/values
        if re.match(
            r"^(GET|POST|PUT|HEAD|OPTIONS|DELETE|PATCH)\s+\S+\s+HTTP/",
            str(arg),
            re.IGNORECASE,
        ):
            continue
        if arg in {"-u", "--url"} and index + 1 < len(normalized):
            # Ignore pre-expanded playbook hosts; always use canonical HTTPS (+ FUZZ).
            skip_next = True
            continue
        if arg in {"-w", "--wordlist"} and index + 1 < len(normalized):
            wordlist = str(normalized[index + 1]).split()[0]
            # Strip accidental "HTTP/1.1" debris from wordlist path
            wordlist = wordlist.split("HTTP/")[0].strip()
            if not wordlist.startswith("/") and not os.path.isfile(wordlist):
                wordlist = WORDLIST
            fixed.extend([arg, _WORDLIST_ALIASES.get(wordlist, wordlist)])
            skip_next = True
            continue
        if isinstance(arg, str) and arg in _WORDLIST_ALIASES:
            fixed.append(_WORDLIST_ALIASES[arg])
            continue
        # Drop bare host/URL tokens that are not flags
        if isinstance(arg, str) and not arg.startswith("-"):
            if "://" in arg or arg.lower().endswith(("http/1.0", "http/1.1", "http/2")):
                continue
        fixed.append(arg)

    if "-w" not in fixed and "--wordlist" not in fixed:
        if os.path.isfile(WORDLIST):
            fixed.extend(["-w", WORDLIST])
        else:
            # Ephemeral fallback so LLM /dev/shm paths don't break the run
            fallback = "/tmp/firebreak-ffuf-words.txt"
            try:
                with open(fallback, "w", encoding="utf-8") as handle:
                    handle.write("admin\nlogin\napi\nrobots.txt\n.git\n")
                fixed.extend(["-w", fallback])
            except OSError:
                pass
    if "-ac" not in fixed and "--auto-calibrate" not in fixed:
        fixed.append("-ac")
    if evasion.get("random_headers", False):
        headers = build_evasion_headers(evasion, target=url)
        for key, value in headers.items():
            if "HTTP/" in str(value) or "\n" in str(value) or "\r" in str(value):
                continue
            fixed.extend(["-H", f"{key}: {value}"])
    fixed = _cdn_backoff(fixed, evasion)
    if "-maxtime" not in fixed and "--maxtime" not in fixed:
        fixed = _set_maxtime(fixed, _compute_maxtime(fixed))
    elif not _stealthy_evasion(evasion):
        idx = fixed.index("-maxtime") if "-maxtime" in fixed else fixed.index("--maxtime")
        try:
            current = int(fixed[idx + 1])
        except (ValueError, IndexError):
            current = 60
        budget = _compute_maxtime(fixed)
        if current < budget:
            fixed = _set_maxtime(fixed, budget)
    return force_url_arg(fixed, url, flags=("-u", "--url"), with_fuzz=True)


def _parse_results(output: str) -> list[dict]:
    results: list[dict] = []
    for raw_line in (output or "").splitlines():
        line = _ANSI_RE.sub("", raw_line).strip()
        if "Status:" not in line:
            continue
        match = _RESULT_RE.search(line)
        if not match:
            continue
        path = match.group("path").strip()
        if path.startswith(":: Progress"):
            continue
        if not path:
            path = "/"
        results.append(
            {
                "path": path,
                "status": match.group("status"),
                "size": match.group("size"),
            }
        )
    return results


def _annotate_runtime(payload: dict, output: str) -> dict:
    stats = _progress_stats(output)
    if stats["total"] > 0:
        payload["progress"] = stats
    if _hit_maxtime(output):
        payload["timed_out"] = True
        payload["partial"] = stats["done"] > 0 or bool(payload.get("results"))
        if payload["partial"] and not payload.get("results"):
            payload.setdefault(
                "note",
                "ffuf hit the runtime limit before finishing the wordlist",
            )
    return payload


def scan(
    target,
    args=None,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion=None,
):
    if evasion is None:
        evasion = {}
    url = _url(target)
    resolved, meta = proxy_meta("ffuf", use_proxy, proxy_protocol)
    if args is None:
        args = [
            "-u",
            f"{url}/FUZZ",
            "-w",
            WORDLIST,
            "-mc",
            "200,301,302,401,403",
            "-ac",
        ]
        if evasion.get("random_headers", False):
            headers = build_evasion_headers(evasion, target=url)
            for key, value in headers.items():
                args.extend(["-H", f"{key}: {value}"])
        args = _cdn_backoff(args, evasion)
        if "-maxtime" not in args and "--maxtime" not in args:
            args = _set_maxtime(args, _compute_maxtime(args))
    else:
        args = _normalize_args(list(args), url, evasion)
    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )

    cmd = ["ffuf", *args, *resolved["flags"]]
    env = merge_env(resolved["env"])
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True, env=env
        )
        results = _parse_results(output)
        payload = _annotate_runtime(
            {
                "tool": "ffuf",
                "target": url,
                "results": results,
                "raw_output": output,
                "proxy": meta,
            },
            output,
        )
        if not results and _looks_like_cdn_stall(output):
            payload["stalled"] = True
            payload["error"] = (
                "ffuf stalled under CDN/WAF rate limits (0 req/sec); "
                "use gobuster results or rerun with Stealth off"
            )
        return payload
    except FileNotFoundError:
        return {
            "tool": "ffuf",
            "target": url,
            "error": "ffuf binary not found",
            "proxy": meta,
        }
    except subprocess.CalledProcessError as e:
        output = str(e.output or "")
        results = _parse_results(output)
        payload = _annotate_runtime(
            {
                "tool": "ffuf",
                "target": url,
                "results": results,
                "raw_output": output,
                "proxy": meta,
            },
            output,
        )
        if results:
            return payload
        if _looks_like_cdn_stall(output):
            payload["stalled"] = True
            payload["error"] = (
                "ffuf stalled under CDN/WAF rate limits (0 req/sec); "
                "use gobuster results or rerun with Stealth off"
            )
        else:
            payload["error"] = output or str(e)
        return payload
