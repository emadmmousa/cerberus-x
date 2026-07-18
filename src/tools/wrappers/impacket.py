import shutil
import subprocess
from urllib.parse import urlparse

DEFAULT_TIMEOUT_SECONDS = 45


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _command() -> str | None:
    for candidate in (
        "impacket-rpcdump",
        "rpcdump.py",
        "impacket-secretsdump",
        "secretsdump.py",
    ):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    host = _host(target)
    binary = _command()
    if binary is None:
        return {"tool": "impacket", "target": host, "error": "impacket not installed"}

    # Default to unauthenticated RPC dump — works as a probe without credentials.
    if args is None:
        if "rpcdump" in binary:
            args = [host]
        else:
            args = [host]
    else:
        args = [
            arg.replace("{{target}}", host) if isinstance(arg, str) else arg
            for arg in args
        ]

    cmd = [binary, *args]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        result = {
            "tool": "impacket",
            "target": host,
            "binary": binary,
            "raw_output": output,
        }
        if completed.returncode != 0 and not output.strip():
            result["error"] = f"impacket exited with code {completed.returncode}"
        return result
    except FileNotFoundError:
        return {"tool": "impacket", "target": host, "error": "impacket not installed"}
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "tool": "impacket",
            "target": host,
            "binary": binary,
            "raw_output": output,
            "error": f"impacket timed out after {timeout}s",
        }
