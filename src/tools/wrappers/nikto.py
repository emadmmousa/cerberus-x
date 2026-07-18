import subprocess
from urllib.parse import urlparse

DEFAULT_TIMEOUT_SECONDS = 120


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    url = _url(target)
    if args is None:
        args = ["-ssl", "-port", "443", "-maxtime", "60"]
    else:
        args = list(args)

    cmd = ["nikto", "-host", url, *args]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        issues = [line.strip() for line in output.splitlines() if line.strip().startswith("+")]
        result = {
            "tool": "nikto",
            "target": url,
            "issues": issues,
            "raw_output": output,
        }
        if completed.returncode != 0 and not output.strip():
            result["error"] = f"nikto exited with code {completed.returncode}"
        return result
    except FileNotFoundError:
        return {"tool": "nikto", "target": url, "error": "nikto binary not found"}
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "tool": "nikto",
            "target": url,
            "issues": [line.strip() for line in output.splitlines() if line.strip().startswith("+")],
            "raw_output": output,
            "error": f"nikto timed out after {timeout}s",
        }
