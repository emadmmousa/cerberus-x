"""ProjectDiscovery subfinder — passive subdomain scraping."""

from __future__ import annotations

import os
import shutil
import subprocess

from tools.osint_scrape import parse_seeds, pick_harvest_domain, skip_result, strip_osint_seed_args

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_SUBFINDER_TIMEOUT", "120"))


def _binary() -> str:
    return shutil.which("subfinder") or "subfinder"


def scan(target, args=None, evasion=None):
    del evasion
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    domain = pick_harvest_domain(target, seeds)
    if not domain:
        return skip_result(
            "subfinder",
            target,
            seeds=seeds,
            note="Subdomain scraping requires a domain or email domain seed.",
        )

    argv = list(cli_args) if cli_args else ["-silent"]
    if "-d" in argv:
        idx = argv.index("-d")
        if idx + 1 < len(argv):
            argv[idx + 1] = domain
    else:
        argv = ["-d", domain, *argv]

    cmd = [_binary(), *argv]
    try:
        output = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )
        hosts = sorted({line.strip().lower() for line in output.splitlines() if line.strip() and "." in line})
        return {
            "tool": "subfinder",
            "target": domain,
            "seeds": seeds,
            "subdomains": hosts[:500],
            "subdomain_count": len(hosts),
            "raw_output": output[:20000],
            "productive": bool(hosts),
        }
    except FileNotFoundError:
        return {"tool": "subfinder", "target": domain, "error": "subfinder is not installed", "productive": False}
    except subprocess.TimeoutExpired:
        return {
            "tool": "subfinder",
            "target": domain,
            "error": f"subfinder timed out after {DEFAULT_TIMEOUT_SECONDS}s",
            "partial": True,
            "productive": False,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "tool": "subfinder",
            "target": domain,
            "error": str(exc.output or exc)[:500],
            "raw_output": (exc.output or "")[:20000],
            "productive": False,
        }
