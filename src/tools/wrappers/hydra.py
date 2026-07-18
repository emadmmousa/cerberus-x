import os
import re
import subprocess
import tempfile
from urllib.parse import urlparse

DEFAULT_SERVICE = "ssh"
DEFAULT_LOGIN = "admin"
DEFAULT_TIMEOUT_SECONDS = 60
_WORDLIST_CANDIDATES = (
    "/usr/share/nmap/nselib/data/passwords.lst",
    "/usr/share/john/password.lst",
    "/usr/share/wordlists/rockyou.txt",
)
_SERVICE_URL_RE = re.compile(r"^([a-z0-9-]+)://", re.IGNORECASE)
_CRED_RE = re.compile(
    r"login:\s*(\S+)\s+password:\s*(\S+)",
    re.IGNORECASE,
)


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _default_wordlist() -> str:
    for path in _WORDLIST_CANDIDATES:
        if os.path.isfile(path):
            return path
    handle = tempfile.NamedTemporaryFile(
        prefix="hydra-pass-",
        suffix=".txt",
        delete=False,
        mode="w",
        encoding="utf-8",
    )
    with handle:
        handle.write("admin\npassword\nPassword1\n123456\nroot\n")
    return handle.name


def _service_from_url_arg(arg: str) -> str | None:
    match = _SERVICE_URL_RE.match(arg)
    return match.group(1).lower() if match else None


def _normalize_service_url(arg: str, host: str) -> str:
    match = _SERVICE_URL_RE.match(arg)
    if not match:
        return arg
    service = match.group(1)
    rest = arg.split("://", 1)[1]
    # Keep explicit port/path if present after the original host segment.
    if "/" in rest:
        _, path = rest.split("/", 1)
        suffix = f"/{path}"
    else:
        suffix = ""
    if ":" in rest.split("/", 1)[0]:
        port = rest.split("/", 1)[0].rsplit(":", 1)[1]
        if port.isdigit():
            return f"{service}://{host}:{port}{suffix}"
    return f"{service}://{host}{suffix}"


def _build_command(target: str, args: list[str] | None) -> tuple[str, str, list[str]]:
    host = _host(target)

    if not args:
        wordlist = _default_wordlist()
        service = DEFAULT_SERVICE
        command = [
            "hydra",
            "-l",
            DEFAULT_LOGIN,
            "-P",
            wordlist,
            "-t",
            "4",
            "-f",
            host,
            service,
        ]
        return host, service, command

    args = [
        _normalize_service_url(arg, host) if isinstance(arg, str) else arg
        for arg in args
    ]

    # Native Hydra style: options... service://host
    for arg in args:
        service = _service_from_url_arg(str(arg))
        if service:
            return host, service, ["hydra", *args]

    # Wrapper style: service first, then options.
    first = str(args[0])
    if first and not first.startswith("-"):
        service = first
        options = list(args[1:])
        return host, service, ["hydra", *options, host, service]

    # Options only — default to ssh against the normalized host.
    return host, DEFAULT_SERVICE, ["hydra", *args, host, DEFAULT_SERVICE]


def _parse_credentials(output: str) -> list[dict]:
    found = []
    for match in _CRED_RE.finditer(output or ""):
        found.append({"login": match.group(1), "password": match.group(2)})
    return found


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    host, service, command = _build_command(target, list(args) if args else None)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        result = {
            "tool": "hydra",
            "target": host,
            "service": service,
            "credentials": _parse_credentials(output),
            "raw_output": output,
        }
        # Hydra often exits non-zero when no valid login is found; treat that as
        # a completed run unless there is no usable output at all.
        if completed.returncode != 0 and not output.strip():
            result["error"] = f"hydra exited with code {completed.returncode}"
        return result
    except FileNotFoundError:
        return {
            "tool": "hydra",
            "target": host,
            "service": service,
            "error": "hydra binary not found",
        }
    except subprocess.TimeoutExpired as exc:
        output = ""
        if isinstance(exc.stdout, str):
            output += exc.stdout
        if isinstance(exc.stderr, str):
            output += exc.stderr
        return {
            "tool": "hydra",
            "target": host,
            "service": service,
            "credentials": _parse_credentials(output),
            "raw_output": output,
            "error": f"hydra timed out after {timeout}s",
        }
