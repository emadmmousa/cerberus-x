import subprocess

from tools.wrappers._proxy import merge_env, proxy_meta


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def scan(target, args=None, use_proxy: bool = False, proxy_protocol: str = "http"):
    url = _url(target)
    resolved, meta = proxy_meta("sqlmap", use_proxy, proxy_protocol)
    if args is None:
        args = ["--batch", "--level=2"]
    else:
        args = list(args)
        if "--batch" not in args and "-b" not in args:
            args = ["--batch", *args]
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
