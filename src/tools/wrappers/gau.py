"""ProjectDiscovery gau — archive and passive URL scraping."""

from __future__ import annotations

import os
import shutil
import subprocess

from tools.osint_scrape import parse_seeds, pick_harvest_domain, skip_result, strip_osint_seed_args

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_GAU_TIMEOUT", "120"))


def _binary() -> str:
    return shutil.which("gau") or "gau"


def scan(target, args=None, evasion=None):
    del evasion
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    domain = pick_harvest_domain(target, seeds)
    if not domain:
        return skip_result(
            "gau",
            target,
            seeds=seeds,
            note="Archive URL scraping requires a domain or email domain seed.",
        )

    argv = list(cli_args) if cli_args else ["--subs"]
    if domain not in argv and "--json" not in argv:
        argv = [domain, *argv]

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
            "tool": "gau",
            "target": domain,
            "seeds": seeds,
            "urls": urls[:500],
            "url_count": len(urls),
            "raw_output": output[:20000],
            "productive": bool(urls),
        }
    except FileNotFoundError:
        return {"tool": "gau", "target": domain, "error": "gau is not installed", "productive": False}
    except subprocess.TimeoutExpired:
        return {
            "tool": "gau",
            "target": domain,
            "error": f"gau timed out after {DEFAULT_TIMEOUT_SECONDS}s",
            "partial": True,
            "productive": False,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "tool": "gau",
            "target": domain,
            "error": str(exc.output or exc)[:500],
            "raw_output": (exc.output or "")[:20000],
            "productive": False,
        }
