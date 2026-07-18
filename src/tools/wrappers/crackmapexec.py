import shutil
import subprocess
from urllib.parse import urlparse

DEFAULT_TIMEOUT_SECONDS = 60


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _command() -> str | None:
    for candidate in ("crackmapexec", "nxc", "cme"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    host = _host(target)
    binary = _command()
    if binary is None:
        return {
            "tool": "crackmapexec",
            "target": host,
            "error": "crackmapexec not found",
        }

    if args is None:
        # Lightweight SMB probe; guest/empty often fails but proves the tool runs.
        args = ["smb", host, "-u", "guest", "-p", "", "--shares"]
    else:
        args = [
            arg.replace("{{target}}", host) if isinstance(arg, str) else arg
            for arg in args
        ]
        # Playbook style often omits inserting host; ensure host is present.
        if host not in args and f"//{host}" not in " ".join(str(a) for a in args):
            # Insert host after protocol if first token is a protocol module.
            if args and not str(args[0]).startswith("-"):
                args = [args[0], host, *args[1:]]
            else:
                args = [host, *args]

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
        results = [
            line.strip()
            for line in output.splitlines()
            if "Pwn3d!" in line or "Status:" in line or "SMB" in line
        ]
        result = {
            "tool": "crackmapexec",
            "target": host,
            "binary": binary,
            "results": results,
            "raw_output": output,
        }
        if completed.returncode != 0 and not output.strip():
            result["error"] = f"crackmapexec exited with code {completed.returncode}"
        return result
    except FileNotFoundError:
        return {
            "tool": "crackmapexec",
            "target": host,
            "error": "crackmapexec not found",
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "tool": "crackmapexec",
            "target": host,
            "binary": binary,
            "results": [],
            "raw_output": output,
            "error": f"crackmapexec timed out after {timeout}s",
        }
