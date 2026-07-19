import subprocess

from tools.waf_evasion import random_delay, random_headers
from tools.wrappers._proxy import merge_env, proxy_meta

DEFAULT_TIMEOUT_SECONDS = 90


def _url(target: str) -> str:
    if "://" in target:
        url = target
    else:
        url = f"https://{target}"
    if "?" not in url:
        url = f"{url.rstrip('/')}/?q=test"
    return url


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
    resolved, meta = proxy_meta("xsstrike", use_proxy, proxy_protocol)
    if args is None:
        args = ["--crawl", "1", "--threads", "5"]
    else:
        args = list(args)
    if evasion.get("random_headers", False):
        headers = random_headers()
        header_str = ",".join(f"{key}: {value}" for key, value in headers.items())
        args.extend(["--headers", header_str])
    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )

    cmd = ["xsstrike", "-u", url, *args, *resolved["flags"]]
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
            "proxy": meta,
        }
        if (
            completed.returncode != 0
            or "Unable to connect to the target" in output
            or "Traceback (most recent call last)" in output
        ):
            if not findings:
                result["error"] = (
                    "xsstrike failed to connect or crashed while probing the target"
                )
            elif completed.returncode != 0 and not output.strip():
                result["error"] = f"xsstrike exited with code {completed.returncode}"
        return result
    except FileNotFoundError:
        return {
            "tool": "xsstrike",
            "target": url,
            "error": "xsstrike binary not found",
            "proxy": meta,
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return {
            "tool": "xsstrike",
            "target": url,
            "findings": [],
            "raw_output": output,
            "error": f"xsstrike timed out after {timeout}s",
            "proxy": meta,
        }
