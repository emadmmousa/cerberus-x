import subprocess

from tools.wrappers._proxy import merge_env, proxy_meta
from tools.wrappers._web_url import canonicalize_web_url


def _url(target: str) -> str:
    return canonicalize_web_url(target)


def scan(target, args=None, use_proxy: bool = False, proxy_protocol: str = "http"):
    url = _url(target)
    resolved, meta = proxy_meta("whatweb", use_proxy, proxy_protocol)
    if args is None:
        args = ["-a", "3"]
    cmd = ["whatweb", *args, *resolved["flags"], url]
    env = merge_env(resolved["env"])
    try:
        output = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            timeout=45,
        )
        return {
            "tool": "whatweb",
            "target": url,
            "raw_output": output,
            "proxy": meta,
        }
    except FileNotFoundError:
        return {
            "tool": "whatweb",
            "target": url,
            "error": "whatweb binary not found",
            "proxy": meta,
        }
    except subprocess.TimeoutExpired:
        return {
            "tool": "whatweb",
            "target": url,
            "error": "whatweb timed out after 45s",
            "raw_output": "ERROR Opening: execution expired (wrapper timeout)",
            "proxy": meta,
        }
    except subprocess.CalledProcessError as e:
        return {
            "tool": "whatweb",
            "target": url,
            "error": str(e.output),
            "proxy": meta,
        }
