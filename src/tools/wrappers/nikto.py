import subprocess
from urllib.parse import urlparse

from tools.waf_evasion import random_delay, random_headers
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TIMEOUT_SECONDS = 120


def _url(target: str) -> str:
    return canonicalize_web_url(target)


def _normalize_args(url: str, args: list[str], evasion=None) -> list[str]:
    """Drop -port/-ssl when -host is already a full URI (Nikto rejects that combo)."""
    if evasion is None:
        evasion = {}
    normalized: list[str] = []
    skip_next = False
    parsed = urlparse(url)
    has_scheme = bool(parsed.scheme)

    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if has_scheme and arg in {"-port", "-p", "-ssl"}:
            if arg in {"-port", "-p"} and index + 1 < len(args):
                skip_next = True
            continue
        if has_scheme and (arg.startswith("-port=") or arg.startswith("-p=")):
            continue
        normalized.append(arg)

    if "-maxtime" not in normalized and not any(
        str(arg).startswith("-maxtime=") for arg in normalized
    ):
        normalized.extend(["-maxtime", "60"])
    if evasion.get("random_headers", False):
        headers = random_headers()
        for key, value in headers.items():
            # Nikto 2.5+ uses -Add-header (not -header).
            normalized.extend(["-Add-header", f"{key}: {value}"])
    return normalized


def scan(
    target,
    args=None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion=None,
):
    if evasion is None:
        evasion = {}
    url = _url(target)
    resolved, meta = proxy_meta("nikto", use_proxy, proxy_protocol)
    if args is None:
        args = ["-maxtime", "60"]
    else:
        args = _normalize_args(url, list(args), evasion)
    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )

    cmd = ["nikto", "-host", url, *args, *resolved["flags"]]
    env = merge_env(resolved["env"])
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
            env=env,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        issues = [
            line.strip()
            for line in output.splitlines()
            if line.strip().startswith("+")
        ]
        result = {
            "tool": "nikto",
            "target": url,
            "issues": issues,
            "raw_output": output,
            "proxy": meta,
        }
        if completed.returncode != 0 and not output.strip():
            result["error"] = f"nikto exited with code {completed.returncode}"
        elif "ERROR:" in output and not issues:
            error_line = next(
                (
                    line.strip()
                    for line in output.splitlines()
                    if line.strip().startswith("- ERROR:")
                    or line.strip().startswith("ERROR:")
                ),
                None,
            )
            if error_line:
                result["error"] = error_line.lstrip("- ").strip()
        return result
    except FileNotFoundError:
        return {
            "tool": "nikto",
            "target": url,
            "error": "nikto binary not found",
            "proxy": meta,
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "tool": "nikto",
            "target": url,
            "issues": [
                line.strip()
                for line in output.splitlines()
                if line.strip().startswith("+")
            ],
            "raw_output": output,
            "error": f"nikto timed out after {timeout}s",
            "proxy": meta,
        }
