"""Sherlock — aggressive username presence scrape across public sites."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from tools.osint_scrape import parse_seeds, pick_username, skip_result, strip_osint_seed_args

DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("FIREBREAK_SHERLOCK_TIMEOUT", "180"))
_FOUND_RE = re.compile(r"\[\+\]\s+(\S+):\s+(https?://\S+)")


def _binary() -> str:
    return shutil.which("sherlock") or "sherlock"


def scan(target, args=None, evasion=None):
    del evasion
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    username = pick_username(target, seeds)
    if not username:
        return skip_result(
            "sherlock",
            target,
            seeds=seeds,
            note="Username scraping requires a username, email, or social profile handle seed.",
        )

    argv = list(cli_args) if cli_args else ["--print-found", "--no-color"]
    if username not in argv and not any(a.startswith("-") for a in argv[:1]):
        argv = [username, *argv]
    elif username not in argv:
        argv = [username, *argv]

    cmd = [_binary(), *argv]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT_SECONDS,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        profiles: list[dict[str, str]] = []
        for match in _FOUND_RE.finditer(output):
            profiles.append({"site": match.group(1), "url": match.group(2)})
        # Sherlock JSON output when --json flag is used
        if not profiles and "--json" in argv:
            try:
                blob = json.loads(completed.stdout or "{}")
                if isinstance(blob, dict):
                    for site, row in blob.items():
                        if isinstance(row, dict) and row.get("url_user"):
                            profiles.append({"site": str(site), "url": str(row["url_user"])})
            except json.JSONDecodeError:
                pass
        return {
            "tool": "sherlock",
            "target": username,
            "seeds": seeds,
            "profiles": profiles[:200],
            "profile_count": len(profiles),
            "raw_output": output[:20000],
            "returncode": completed.returncode,
            "productive": bool(profiles),
        }
    except FileNotFoundError:
        return {"tool": "sherlock", "target": username, "error": "sherlock is not installed", "productive": False}
    except subprocess.TimeoutExpired:
        return {
            "tool": "sherlock",
            "target": username,
            "error": f"sherlock timed out after {DEFAULT_TIMEOUT_SECONDS}s",
            "partial": True,
            "productive": False,
        }
