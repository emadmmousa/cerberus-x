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
        return {
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
