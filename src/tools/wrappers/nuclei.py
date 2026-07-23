import os
import re
import subprocess

from tools.waf_evasion import build_evasion_headers, random_delay
from tools.wrappers._argv import coerce_argv
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_NUCLEI_TIMEOUT", "240"))

TEMPLATE_ROOTS = (
    os.environ.get("NUCLEI_TEMPLATES_DIR", "/root/nuclei-templates"),
    "/home/nuclei/nuclei-templates",
    os.path.expanduser("~/nuclei-templates"),
)

# LLM often invents -template; nuclei wants -t / --templates
_TEMPLATE_FLAGS = {"-t", "--templates", "-template", "--template", "-templates"}


def _url(target: str) -> str:
    return canonicalize_web_url(target)


def _resolve_template_arg(value: str) -> str:
    if not value or value.startswith("/") or os.path.isdir(value) or os.path.isfile(value):
        return value
    candidates = [
        value,
        value.lstrip("./"),
        f"http/{value.lstrip('/')}",
        f"http/cves/{value.lstrip('/')}" if value not in {"cves", "cves/"} else "http/cves",
    ]
    for root in TEMPLATE_ROOTS:
        if not root:
            continue
        for candidate in candidates:
            path = os.path.join(root, candidate)
            if os.path.isdir(path) or os.path.isfile(path):
                return path
            if not candidate.endswith("/") and os.path.isdir(f"{path}/"):
                return f"{path}/"
    return os.path.join(TEMPLATE_ROOTS[0], "http/cves/")


def _normalize_args(args: list[str], evasion=None) -> list[str]:
    if evasion is None:
        evasion = {}
    args = coerce_argv(args)
    normalized: list[str] = []
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        # Rewrite LLM aliases to real nuclei flags
        if arg in _TEMPLATE_FLAGS or arg.startswith("-template=") or arg.startswith(
            "--template="
        ):
            if "=" in arg:
                value = arg.split("=", 1)[1]
                normalized.extend(["-t", _resolve_template_arg(value)])
                continue
            if index + 1 < len(args) and not str(args[index + 1]).startswith("-"):
                normalized.extend(["-t", _resolve_template_arg(str(args[index + 1]))])
                skip_next = True
            continue
        if arg in ("-t", "--templates"):
            if index + 1 < len(args):
                normalized.extend(["-t", _resolve_template_arg(str(args[index + 1]))])
                skip_next = True
            continue
        if arg.startswith("--templates="):
            _key, value = arg.split("=", 1)
            normalized.append(f"--templates={_resolve_template_arg(value)}")
            continue
        normalized.append(arg)
    if evasion.get("random_headers", False):
        headers = build_evasion_headers(evasion)
        for key, value in headers.items():
            if "HTTP/" in str(value):
                continue
            normalized.extend(["-H", f"{key}: {value}"])
    return normalized


def scan(
    target,
    args=None,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion=None,
):
    if evasion is None:
        evasion = {}
    url = _url(target)
    resolved, meta = proxy_meta("nuclei", use_proxy, proxy_protocol)
    if args is None:
        args = [
            "-t",
            _resolve_template_arg("http/cves/"),
            "-severity",
            "critical,high",
            "-silent",
        ]
    else:
        args = _normalize_args(list(args), evasion)
        if "-t" not in args and "--templates" not in args and not any(
            str(arg).startswith("--templates=") for arg in args
        ):
            args = ["-t", _resolve_template_arg("http/cves/"), *args]
        if "-silent" not in args and "--silent" not in args:
            args = [*args, "-silent"]
    if "-timeout" not in args and not any(str(a).startswith("-timeout=") for a in args):
        args = [*args, "-timeout", "12"]
    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )

    cmd = ["nuclei", "-u", url, *args, *resolved["flags"]]
    env = merge_env(resolved["env"])
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            start_new_session=True,
            env=env,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode != 0 and not output.strip():
            return {
                "tool": "nuclei",
                "target": url,
                "error": f"nuclei exited with code {completed.returncode}",
                "proxy": meta,
            }
    except FileNotFoundError as e:
        return {
            "tool": "nuclei",
            "target": url,
            "error": str(e),
            "proxy": meta,
        }
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        findings = []
        ansi = re.compile(r"\x1b\[[0-9;]*m")
        allowed = {"info", "low", "medium", "high", "critical", "unknown"}
        for line in output.split("\n"):
            clean = ansi.sub("", line).strip()
            if "[" not in clean or "]" not in clean:
                continue
            match = re.match(
                r"^\[(?P<severity>[^\]]+)\]\s+(?P<title>.+?)\s*(?:\[(?P<protocol>[^\]]+)\])?\s*(?P<url>https?://\S+)?\s*$",
                clean,
            )
            if match and match.group("severity").strip().lower() in allowed:
                findings.append({"severity": match.group("severity").strip().lower(), "title": match.group("title").strip()})
        payload = {
            "tool": "nuclei",
            "target": url,
            "findings": findings,
            "raw_output": output,
            "partial": True,
            "error": f"nuclei timed out after {DEFAULT_TIMEOUT_SECONDS}s",
            "proxy": meta,
        }
        if findings:
            return payload
        return payload

    findings = []
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    allowed = {"info", "low", "medium", "high", "critical", "unknown"}
    for line in output.split("\n"):
        clean = ansi.sub("", line).strip()
        if "[" not in clean or "]" not in clean:
            continue
        if any(
            marker in clean
            for marker in (
                "Could not find template",
                "Current nuclei version",
                "Current nuclei-templates",
                "New templates added",
                "Templates loaded",
                "Executing ",
                "Targets loaded",
                "Templates clustered",
                "Skipped ",
                "Using Interactsh",
                "Scan completed",
                "Could not run nuclei",
                "no templates provided",
                "No results found",
                "flag provided but not defined",
            )
        ):
            continue
        match = re.match(
            r"^\[(?P<severity>[^\]]+)\]\s+(?P<title>.+?)\s*(?:\[(?P<protocol>[^\]]+)\])?\s*(?P<url>https?://\S+)?\s*$",
            clean,
        )
        if not match:
            continue
        severity = match.group("severity").strip().lower()
        title = match.group("title").strip()
        if severity not in allowed or not title:
            continue
        finding = {"severity": severity, "title": title}
        if match.group("url"):
            finding["url"] = match.group("url")
        cve_hit = re.search(r"CVE-\d{4}-\d+", title, re.IGNORECASE)
        if cve_hit:
            finding["template_id"] = cve_hit.group(0).upper()
        findings.append(finding)

    if "flag provided but not defined" in output.lower() and not findings:
        return {
            "tool": "nuclei",
            "target": url,
            "findings": [],
            "error": output.strip().splitlines()[0]
            if output.strip()
            else "invalid nuclei flags",
            "raw_output": output,
            "proxy": meta,
        }
    return {
        "tool": "nuclei",
        "target": url,
        "findings": findings,
        "raw_output": output,
        "proxy": meta,
    }
