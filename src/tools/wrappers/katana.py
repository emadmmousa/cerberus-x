"""ProjectDiscovery katana web crawler wrapper."""

from __future__ import annotations

import os
import shutil
import subprocess

from tools.osint_scrape import parse_seeds, pick_web_url, skip_result, strip_osint_seed_args
from tools.wrappers._web_url import canonicalize_web_url

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_KATANA_TIMEOUT", "180"))


def _binary() -> str:
    return shutil.which("katana") or "katana"


def scan(
    target,
    args=None,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion=None,
):
    del use_proxy, proxy_protocol, evasion
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    url = pick_web_url(target, seeds)
    if not url:
        return skip_result(
            "katana",
            target,
            seeds=seeds,
            note="Web crawling requires a domain, URL, or social profile seed.",
        )
    url = canonicalize_web_url(url)
    argv = list(cli_args) if cli_args else ["-d", "3", "-jc", "-silent"]
    if "-u" not in argv:
        argv = ["-u", url, *argv]
    else:
        idx = argv.index("-u")
        if idx + 1 < len(argv):
            argv[idx + 1] = canonicalize_web_url(str(argv[idx + 1]))
    cmd = [_binary(), *argv]
    try:
        output = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        urls = sorted({line.strip() for line in output.splitlines() if line.strip().startswith("http")})
        return {
            "tool": "katana",
            "target": url,
            "urls": urls[:500],
            "url_count": len(urls),
            "raw_output": output[:20000],
            "productive": bool(urls),
        }
    except FileNotFoundError:
        return {"tool": "katana", "target": url, "error": "katana is not installed"}
    except subprocess.TimeoutExpired:
        return {
            "tool": "katana",
            "target": url,
            "error": f"katana timed out after {DEFAULT_TIMEOUT_SECONDS}s",
            "partial": True,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "tool": "katana",
            "target": url,
            "error": str(exc.output or exc)[:500],
            "raw_output": (exc.output or "")[:20000],
        }
