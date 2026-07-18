import re
import subprocess
import uuid
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WORDLIST = "/usr/share/dirb/wordlists/common.txt"
_WILDCARD_LENGTH_RE = re.compile(r"Length:\s*(\d+)", re.IGNORECASE)


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def _probe_exclude_length(url: str) -> int | None:
    """Measure response body length for a random path (CDN/wildcard detection)."""
    probe = f"{url.rstrip('/')}/{uuid.uuid4()}"
    req = Request(probe, headers={"User-Agent": "gobuster/3.6"})
    ctx = ssl.create_default_context()
    try:
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


def _run(args: list[str]) -> str:
    return subprocess.check_output(["gobuster", *args], stderr=subprocess.STDOUT, text=True)


def scan(target, args=None):
    url = _url(target)
    if args is None:
        args = ["dir", "-u", url, "-w", WORDLIST, "-q", "-t", "20", "-b", "404"]
    else:
        args = [
            arg.replace("{{target}}", url) if isinstance(arg, str) else arg
            for arg in args
        ]

    args = list(args)
    if "--exclude-length" not in args and not any(
        a.startswith("--exclude-length=") for a in args
    ):
        length = _probe_exclude_length(url)
        if length is not None:
            args = _with_exclude_length(args, length)

    try:
        output = _run(args)
        return {
            "tool": "gobuster",
            "target": url,
            "directories": _parse_directories(output),
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "gobuster", "target": url, "error": "gobuster binary not found"}
    except subprocess.CalledProcessError as exc:
        message = str(exc.output or exc)
        reported = _length_from_error(message)
        if reported is None:
            return {"tool": "gobuster", "target": url, "error": message}
        try:
            output = _run(_with_exclude_length(args, reported))
            return {
                "tool": "gobuster",
                "target": url,
                "directories": _parse_directories(output),
                "raw_output": output,
                "exclude_length": reported,
            }
        except subprocess.CalledProcessError as retry_exc:
            return {
                "tool": "gobuster",
                "target": url,
                "error": str(retry_exc.output or retry_exc),
            }
