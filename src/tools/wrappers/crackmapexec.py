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


def _normalize_args(args: list[str], host: str) -> list[str]:
    normalized = [
        arg.replace("{{target}}", host) if isinstance(arg, str) else arg
        for arg in args
    ]
    fixed: list[str] = []
    for arg in normalized:
        text = str(arg)
        if "://" in text:
            parsed = urlparse(text)
            candidate = parsed.hostname or _host(text)
            fixed.append(candidate)
        else:
            fixed.append(arg)

    # Playbook style often omits inserting host; ensure host is present.
    if host not in {str(arg) for arg in fixed} and f"//{host}" not in " ".join(
        str(arg) for arg in fixed
    ):
        if fixed and not str(fixed[0]).startswith("-"):
            fixed = [fixed[0], host, *fixed[1:]]
        else:
            fixed = [host, *fixed]
    return fixed


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
        args = _normalize_args(list(args), host)

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
        # NetExec/CME exits after first-time workspace bootstrap; run once more.
        if "First time use detected" in output or "Creating home directory structure" in output:
            retry = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                start_new_session=True,
            )
            output = (
                output
                + "\n"
                + ((retry.stdout or "") + (retry.stderr or ""))
            )
            completed = retry
        results = [
            line.strip()
            for line in output.splitlines()
            if "Pwn3d!" in line
            or "Status:" in line
            or "[*]" in line and "SMB" in line
            or "[+]" in line
            or "[-]" in line
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
