import re
import subprocess
import uuid
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from tools.wrappers._proxy import merge_env, proxy_meta

WORDLIST = "/usr/share/dirb/wordlists/common.txt"
_WILDCARD_LENGTH_RE = re.compile(r"Length:\s*(\d+)", re.IGNORECASE)
_WILDCARD_STATUS_RE = re.compile(r"=>\s*(\d{3})\s*\(Length:", re.IGNORECASE)


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def _probe_exclude_length(url: str, env: dict[str, str] | None = None) -> int | None:
    """Measure response body length for a random path (CDN/wildcard detection)."""
    probe = f"{url.rstrip('/')}/{uuid.uuid4()}"
    req = Request(probe, headers={"User-Agent": "gobuster/3.6"})
    ctx = ssl.create_default_context()
    try:
        if env and (env.get("HTTP_PROXY") or env.get("http_proxy")):
            proxy = env.get("HTTPS_PROXY") or env.get("HTTP_PROXY") or env.get("http_proxy")
            opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
            with opener.open(req, timeout=10) as resp:
                return len(resp.read())
        with urlopen(req, timeout=10, context=ctx) as resp:
            return len(resp.read())
    except HTTPError as exc:
        try:
            return len(exc.read() or b"")
        except Exception:
            return None
    except (URLError, TimeoutError, OSError):
        return None


def _without_exclude_length(args: list[str]) -> list[str]:
    cleaned = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--exclude-length":
            skip_next = True
            continue
        if arg.startswith("--exclude-length="):
            continue
        cleaned.append(arg)
    return cleaned


def _with_exclude_length(args: list[str], length: int) -> list[str]:
    return [*_without_exclude_length(args), "--exclude-length", str(length)]


def _parse_directories(output: str) -> list[dict]:
    directories = []
    for line in output.split("\n"):
        if "Status:" not in line and "(Status:" not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        path = parts[0]
        status = None
        for part in parts:
            if part.startswith("(Status:") or part.startswith("Status:"):
                status = part.split(":", 1)[1].rstrip(")")
        if status:
            directories.append({"path": path, "status": status})
    return directories


def _length_from_error(message: str) -> int | None:
    match = _WILDCARD_LENGTH_RE.search(message or "")
    return int(match.group(1)) if match else None


def _status_from_error(message: str) -> str | None:
    match = _WILDCARD_STATUS_RE.search(message or "")
    return match.group(1) if match else None


def _with_blacklist_status(args: list[str], status: str) -> list[str]:
    cleaned: list[str] = []
    skip_next = False
    existing: list[str] = []
    for arg in args:
        if skip_next:
            skip_next = False
            existing = [part for part in str(arg).split(",") if part]
            continue
        if arg in {"-b", "--status-codes-blacklist"}:
            skip_next = True
            continue
        if arg.startswith("--status-codes-blacklist="):
            existing = [
                part
                for part in arg.split("=", 1)[1].split(",")
                if part
            ]
            continue
        cleaned.append(arg)
    codes = sorted(set([*existing, "404", status]), key=lambda value: (len(value), value))
    return [*cleaned, "-b", ",".join(codes)]


def _run(args: list[str], env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(
        ["gobuster", *args], stderr=subprocess.STDOUT, text=True, env=env
    )


def scan(target, args=None, use_proxy: bool = False, proxy_protocol: str = "http"):
    url = _url(target)
    resolved, meta = proxy_meta("gobuster", use_proxy, proxy_protocol)
    env = merge_env(resolved["env"])
    if args is None:
        args = ["dir", "-u", url, "-w", WORDLIST, "-q", "-t", "20", "-b", "404"]
    else:
        args = [
            arg.replace("{{target}}", url) if isinstance(arg, str) else arg
            for arg in args
        ]

    args = list(args)
    args = [*args, *resolved["flags"]]
    if "--exclude-length" not in args and not any(
        a.startswith("--exclude-length=") for a in args
    ):
        length = _probe_exclude_length(url, env)
        if length is not None:
            args = _with_exclude_length(args, length)

    try:
        output = _run(args, env=env)
        return {
            "tool": "gobuster",
            "target": url,
            "directories": _parse_directories(output),
            "raw_output": output,
            "proxy": meta,
        }
    except FileNotFoundError:
        return {
            "tool": "gobuster",
            "target": url,
            "error": "gobuster binary not found",
            "proxy": meta,
        }
    except subprocess.CalledProcessError as exc:
        message = str(exc.output or exc)
        reported = _length_from_error(message)
        status = _status_from_error(message)
        retry_args = list(args)
        if reported is not None:
            retry_args = _with_exclude_length(retry_args, reported)
        if status is not None:
            retry_args = _with_blacklist_status(retry_args, status)
        if reported is None and status is None:
            return {"tool": "gobuster", "target": url, "error": message, "proxy": meta}
        try:
            output = _run(retry_args, env=env)
            result = {
                "tool": "gobuster",
                "target": url,
                "directories": _parse_directories(output),
                "raw_output": output,
                "proxy": meta,
            }
            if reported is not None:
                result["exclude_length"] = reported
            if status is not None:
                result["exclude_status"] = status
            return result
        except subprocess.CalledProcessError as retry_exc:
            return {
                "tool": "gobuster",
                "target": url,
                "error": str(retry_exc.output or retry_exc),
                "proxy": meta,
            }
