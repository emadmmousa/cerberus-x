import subprocess

from tools.sql_injection import (
    build_sqlmap_args,
    resolve_sqli_intensity,
    sqli_profile,
)
from tools.waf_evasion import (
    build_evasion_headers,
    random_delay,
    sqlmap_tamper_for_evasion,
)
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url


def _url(target: str) -> str:
    return canonicalize_web_url(target)


def _sqlmap_ran_injection_tests(output: str) -> bool:
    lowered = (output or "").lower()
    return any(
        needle in lowered
        for needle in (
            "testing if the target url",
            "testing for sql injection",
            "testing '",
            "sql injection point",
            "parameter '",
            "parameters:",
            "appears to be injectable",
            "is vulnerable",
            "target url is not injectable",
            "not injectable",
            "testing connection to the target",
            "heuristic (basic) test shows",
        )
    )


def _analyze_sqlmap_output(output: str, *, vulnerable: bool) -> dict[str, object]:
    """Derive structured flags from sqlmap stdout/stderr."""
    if vulnerable:
        return {}
    lowered = (output or "").lower()
    explicit_no_surface = any(
        phrase in lowered
        for phrase in (
            "no usable links found",
            "no injection point",
            "no parameter(s) found",
            "does not appear to be dynamic",
        )
    )
    crawled = any(
        phrase in lowered
        for phrase in (
            "starting crawler",
            "searching for links with depth",
            "normalize crawling results",
        )
    )
    crawl_without_tests = crawled and not _sqlmap_ran_injection_tests(output)
    no_surface = explicit_no_surface or crawl_without_tests
    waf_blocked = any(
        token in lowered
        for token in (
            "just a moment",
            "cloudflare",
            "403 forbidden",
            "attention required",
            "cf-mitigated",
        )
    )
    flags: dict[str, object] = {}
    if no_surface:
        flags["partial"] = True
        flags["no_injection_surface"] = True
        if crawl_without_tests and not explicit_no_surface:
            flags["note"] = (
                "Crawler finished but sqlmap never reached an injectable parameter — "
                "SQLi check inconclusive."
            )
        else:
            flags["note"] = (
                "No injectable GET parameters or forms found — SQLi check inconclusive."
            )
    if waf_blocked:
        flags["waf_blocked"] = True
        flags["partial"] = True
        flags["note"] = flags.get("note") or (
            "Target may be WAF/CDN blocked — sqlmap could not reach injectable surface."
        )
    return flags


def _infer_dbms(evasion: dict | None, args: list[str]) -> str | None:
    if evasion and evasion.get("dbms"):
        return str(evasion["dbms"])
    for a in args:
        if str(a).startswith("--dbms="):
            return str(a).split("=", 1)[1]
    return None


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
    resolved, meta = proxy_meta("sqlmap", use_proxy, proxy_protocol)
    if args is None:
        args = ["--batch"]
    else:
        args = list(args)
        if "--batch" not in args and "-b" not in args:
            args = ["--batch", *args]

    intensity = resolve_sqli_intensity(evasion)
    profile = sqli_profile(intensity, dbms=_infer_dbms(evasion, args))
    # Overlay playbook args with full technique strategy (preserves user flags).
    args = build_sqlmap_args(profile, existing=args, evasion=evasion)

    if evasion.get("random_headers", False):
        headers = build_evasion_headers(evasion, target=url)
        for key, value in headers.items():
            args.extend(["--header", f"{key}: {value}"])
    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )
        if "--delay" not in args:
            delay = max(0, int(float(evasion.get("random_delay_min") or 0)))
            if delay > 0:
                args.extend(["--delay", str(delay)])
    if (
        (evasion.get("level") == "aggressive" or evasion.get("method_swap"))
        and "--method" not in args
        and not any(str(a).upper() == "POST" for a in args)
    ):
        args.extend(["--method", "POST"])
        if "--forms" not in args:
            args.append("--forms")

    cmd = ["sqlmap", "-u", url, *args, *resolved["flags"]]
    env = merge_env(resolved["env"])
    try:
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, text=True, env=env
        )
        vulnerable = "vulnerable" in output.lower() or "sql injection" in output.lower()
        payload = {
            "tool": "sqlmap",
            "target": url,
            "vulnerable": vulnerable,
            "raw_output": output,
            "proxy": meta,
            "sqli": {
                "intensity": intensity,
                "technique": profile.get("technique"),
                "dbms": profile.get("dbms"),
            },
            "evasion": {
                "level": evasion.get("level"),
                "tamper": sqlmap_tamper_for_evasion(evasion)
                if evasion.get("obfuscate_payloads")
                or intensity in {"high", "aggressive"}
                else None,
            },
        }
        payload.update(_analyze_sqlmap_output(output, vulnerable=vulnerable))
        return payload
    except FileNotFoundError:
        return {
            "tool": "sqlmap",
            "target": url,
            "error": "sqlmap binary not found",
            "proxy": meta,
        }
    except subprocess.CalledProcessError as e:
        return {
            "tool": "sqlmap",
            "target": url,
            "error": str(e.output),
            "proxy": meta,
        }
