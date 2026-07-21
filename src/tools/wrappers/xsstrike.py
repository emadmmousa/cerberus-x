import re
import subprocess
from pathlib import Path

from tools.waf_evasion import build_evasion_headers, random_delay
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TIMEOUT_SECONDS = 90
_XSSTRIKE_ROOT = Path("/opt/XSStrike")
_WAF_DETECTOR = _XSSTRIKE_ROOT / "core" / "wafDetector.py"
_REQUESTER = _XSSTRIKE_ROOT / "core" / "requester.py"


def _url(target: str) -> str:
    url = canonicalize_web_url(target)
    if "?" not in url:
        url = f"{url.rstrip('/')}/?q=test"
    return url


def _headers_arg(headers: dict) -> str:
    """XSStrike extractHeaders() expects newline-separated Header: value lines.

    Comma-joining breaks Accept values that themselves contain commas.
    """
    return "\\n".join(f"{key}: {value}" for key, value in headers.items())


def _ensure_xsstrike_patches() -> None:
    """Harden upstream XSStrike against empty responses (common WAF/hard-drop)."""
    if _WAF_DETECTOR.is_file():
        text = _WAF_DETECTOR.read_text(encoding="utf-8")
        if "firebreak-patch" not in text:
            needle = (
                "    response = requester(url, params, headers, GET, delay, timeout)\n"
                "    page = response.text\n"
                "    code = str(response.status_code)\n"
            )
            patch = (
                "    response = requester(url, params, headers, GET, delay, timeout)\n"
                "    # firebreak-patch: empty Response has status_code None\n"
                "    if response is None or getattr(response, 'status_code', None) is None:\n"
                "        return None\n"
                "    page = response.text or ''\n"
                "    code = str(response.status_code)\n"
            )
            if needle in text:
                try:
                    _WAF_DETECTOR.write_text(
                        text.replace(needle, patch, 1), encoding="utf-8"
                    )
                except OSError:
                    pass

    if _REQUESTER.is_file():
        text = _REQUESTER.read_text(encoding="utf-8")
        if "firebreak-patch" not in text and "time.sleep(600)" in text:
            patched = text.replace(
                "        logger.warning('WAF is dropping suspicious requests.')\n"
                "        logger.warning('Scanning will continue after 10 minutes.')\n"
                "        time.sleep(600)\n",
                "        # firebreak-patch: never sleep 10 minutes in automation\n"
                "        logger.warning('WAF is dropping suspicious requests.')\n"
                "        return requests.Response()\n",
                1,
            )
            if patched != text:
                try:
                    _REQUESTER.write_text(patched, encoding="utf-8")
                except OSError:
                    pass


def _normalize_args(args: list[str], evasion: dict) -> list[str]:
    out = list(args)
    # Drop playbook --headers if present; we inject a safe format below.
    cleaned: list[str] = []
    skip_next = False
    for index, arg in enumerate(out):
        if skip_next:
            skip_next = False
            continue
        if arg in {"--headers", "-H"}:
            if index + 1 < len(out) and not str(out[index + 1]).startswith("-"):
                skip_next = True
            continue
        cleaned.append(arg)
    out = cleaned

    if "--timeout" not in out and not any(
        str(a).startswith("--timeout=") for a in out
    ):
        out.extend(["--timeout", "20"])
    if "--skip" not in out:
        out.append("--skip")
    if evasion.get("random_headers", False):
        # Prefer a browser-like Accept; newline/escaped format for XSStrike parser.
        headers = build_evasion_headers(
            evasion,
            extra={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        # XSStrike does not need Upgrade-Insecure-Requests / Cache-Control.
        headers.pop("Upgrade-Insecure-Requests", None)
        headers.pop("Cache-Control", None)
        out.extend(["--headers", _headers_arg(headers)])
    return out


def _parse_findings(output: str) -> list[str]:
    findings: list[str] = []
    for line in (output or "").splitlines():
        clean = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", line).strip()
        if not clean:
            continue
        if any(
            token in clean
            for token in (
                "Payload:",
                "Vulnerable",
                "Reflections found",
                "WAF detected",
                "No vectors were crafted",
                "No reflection found",
                "No parameters to test",
            )
        ):
            findings.append(clean)
    return findings


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
    _ensure_xsstrike_patches()

    if args is None:
        args = ["--timeout", "20", "--skip", "--threads", "5"]
    args = _normalize_args(list(args), evasion)

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
        findings = _parse_findings(output)
        result = {
            "tool": "xsstrike",
            "target": url,
            "findings": findings,
            "raw_output": output,
            "proxy": meta,
        }
        crashed = "Traceback (most recent call last)" in output
        unable = "Unable to connect to the target" in output
        if crashed or (unable and not findings):
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
            "findings": _parse_findings(output),
            "raw_output": output,
            "error": f"xsstrike timed out after {timeout}s",
            "proxy": meta,
        }
