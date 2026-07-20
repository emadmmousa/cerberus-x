import subprocess

from tools.waf_evasion import random_delay, random_headers
from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url


def _url(target: str) -> str:
    return canonicalize_web_url(target)


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
        args = ["--batch", "--level=2"]
    else:
        args = list(args)
        if "--batch" not in args and "-b" not in args:
            args = ["--batch", *args]
    if evasion.get("random_headers", False):
        headers = random_headers()
        for key, value in headers.items():
            args.extend(["--header", f"{key}: {value}"])
    if evasion.get("random_delay_min", 0) > 0:
        random_delay(
            evasion.get("random_delay_min"), evasion.get("random_delay_max")
        )
    if evasion.get("obfuscate_payloads", False):
        if not any(str(a).startswith("--tamper") for a in args):
            args.extend(["--tamper", "space2comment,randomcase"])
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
