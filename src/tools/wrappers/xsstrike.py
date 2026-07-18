import subprocess

DEFAULT_TIMEOUT_SECONDS = 90


def _url(target: str) -> str:
    if "://" in target:
        url = target
    else:
        url = f"https://{target}"
    if "?" not in url:
        url = f"{url.rstrip('/')}/?q=test"
    return url


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    url = _url(target)
    if args is None:
        # Keep defaults light so smoke tests finish.
        args = ["--crawl", "1", "--threads", "5"]
    else:
        args = list(args)

    cmd = ["xsstrike", "-u", url, *args]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        findings = [
            line.strip()
            for line in output.splitlines()
            if "Payload:" in line or "Vulnerable" in line or "XSS" in line
        ]
        result = {
            "tool": "xsstrike",
            "target": url,
            "findings": findings,
            "raw_output": output,
        }
        if completed.returncode != 0 and not output.strip():
            result["error"] = f"xsstrike exited with code {completed.returncode}"
        return result
    except FileNotFoundError:
        return {"tool": "xsstrike", "target": url, "error": "xsstrike binary not found"}
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "tool": "xsstrike",
            "target": url,
            "findings": [],
            "raw_output": output,
            "error": f"xsstrike timed out after {timeout}s",
        }
