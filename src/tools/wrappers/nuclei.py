import os
import re
import subprocess

TEMPLATE_ROOTS = (
    os.environ.get("NUCLEI_TEMPLATES_DIR", "/root/nuclei-templates"),
    "/home/nuclei/nuclei-templates",
    os.path.expanduser("~/nuclei-templates"),
)


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def _resolve_template_arg(value: str) -> str:
    """Map short template paths like cves/ to installed nuclei-templates dirs."""
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
    # Prefer the canonical CVE tree even if templates were not downloaded yet.
    return os.path.join(TEMPLATE_ROOTS[0], "http/cves/")


def _normalize_args(args: list[str]) -> list[str]:
    normalized: list[str] = []
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in {"-t", "--templates"}:
            if index + 1 < len(args):
                normalized.extend([arg, _resolve_template_arg(str(args[index + 1]))])
                skip_next = True
            continue
        if arg.startswith("--templates="):
            key, value = arg.split("=", 1)
            normalized.append(f"{key}={_resolve_template_arg(value)}")
            continue
        normalized.append(arg)
    return normalized


def scan(target, args=None, use_proxy: bool = False, proxy_protocol: str = "http"):
    from tools.wrappers._proxy import merge_env, proxy_meta

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
        args = _normalize_args(list(args))
        if "-t" not in args and "--templates" not in args and not any(
            str(arg).startswith("--templates=") for arg in args
        ):
            args = ["-t", _resolve_template_arg("http/cves/"), *args]
        if "-silent" not in args and "--silent" not in args:
            args = [*args, "-silent"]

    cmd = ["nuclei", "-u", url, *args, *resolved["flags"]]
    env = merge_env(resolved["env"])
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True, env=env
        )
    except FileNotFoundError:
        return {
            "tool": "nuclei",
            "target": url,
            "error": "nuclei binary not found",
            "proxy": meta,
        }
    except subprocess.CalledProcessError as e:
        output = e.output or ""
        if not output:
            return {
                "tool": "nuclei",
                "target": url,
                "error": str(e),
                "proxy": meta,
            }

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
        findings.append(finding)
    return {
        "tool": "nuclei",
        "target": url,
        "findings": findings,
        "raw_output": output if output.strip() else "no findings",
        "proxy": meta,
    }
