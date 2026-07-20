import os
import re
import subprocess

from tools.waf_evasion import random_delay, random_headers
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url, force_url_arg

WORDLIST = "/usr/share/dirb/wordlists/common.txt"
_WORDLIST_ALIASES = {
    "/usr/share/wordlists/dirb/common.txt": WORDLIST,
    "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt": WORDLIST,
}
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
_RESULT_RE = re.compile(
    r"^(?P<path>.*?)\s*\[Status:\s*(?P<status>\d+)(?:,\s*Size:\s*(?P<size>\d+))?.*?\]",
    re.IGNORECASE,
)


def _url(target: str) -> str:
    return canonicalize_web_url(target).rstrip("/")


def _normalize_args(args: list[str], url: str, evasion=None) -> list[str]:
    if evasion is None:
        evasion = {}
    normalized = [
        arg.replace("{{target}}", url) if isinstance(arg, str) else arg
        for arg in args
    ]
    fixed: list[str] = []
    skip_next = False
    for index, arg in enumerate(normalized):
        if skip_next:
            skip_next = False
            continue
        if arg in {"-u", "--url"} and index + 1 < len(normalized):
            # Ignore pre-expanded playbook hosts; always use canonical HTTPS (+ FUZZ).
            skip_next = True
            continue
        if arg in {"-w", "--wordlist"} and index + 1 < len(normalized):
            wordlist = str(normalized[index + 1])
            fixed.extend([arg, _WORDLIST_ALIASES.get(wordlist, wordlist)])
            skip_next = True
            continue
        if isinstance(arg, str) and arg in _WORDLIST_ALIASES:
            fixed.append(_WORDLIST_ALIASES[arg])
            continue
        fixed.append(arg)

    fixed = force_url_arg(fixed, url, flags=("-u", "--url"), with_fuzz=True)
    if "-w" not in fixed and "--wordlist" not in fixed:
        if os.path.isfile(WORDLIST):
            fixed.extend(["-w", WORDLIST])
    if "-ac" not in fixed and "--auto-calibrate" not in fixed:
        fixed.append("-ac")
    if "-maxtime" not in fixed:
        fixed.extend(["-maxtime", "60"])
    if evasion.get("random_headers", False):
        headers = random_headers()
        for key, value in headers.items():
            fixed.extend(["-H", f"{key}: {value}"])
    return fixed


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
        # Empty FUZZ / blank wordlist line often matches the site root.
        if not path or path.startswith(":: Progress"):
            continue
        results.append(
            {
                "path": path,
                "status": match.group("status"),
                "size": match.group("size"),
            }
        )
    return results


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
            "-maxtime",
            "60",
            "-ac",
        ]
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
        return {
            "tool": "ffuf",
            "target": url,
            "results": _parse_results(output),
            "raw_output": output,
            "proxy": meta,
        }
    except FileNotFoundError:
        return {
            "tool": "ffuf",
            "target": url,
            "error": "ffuf binary not found",
            "proxy": meta,
        }
    except subprocess.CalledProcessError as e:
        return {
            "tool": "ffuf",
            "target": url,
            "error": str(e.output),
            "proxy": meta,
        }
