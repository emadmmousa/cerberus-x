import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse

from tools.osint_scrape import (
    parse_seeds,
    pick_harvest_domain,
    skip_result,
    strip_osint_seed_args,
)

# Banner / author emails that appear in tool stdout, not target intel.
_BANNER_EMAILS = frozenset(
    {
        "cmartorella@edge-security.com",
    }
)


def _domain(target: str) -> str:
    value = target.strip()
    if "://" in value:
        value = urlparse(value).hostname or value
    return value.split("/")[0].split(":")[0]


def _command() -> list[str]:
    for candidate in ("theHarvester", "theharvester"):
        path = shutil.which(candidate)
        if path:
            return [path]
    return [sys.executable, "-m", "theHarvester"]


def scan(target, args=None):
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    domain = pick_harvest_domain(target, seeds)
    if not domain:
        return skip_result(
            "theHarvester",
            target,
            seeds=seeds,
            note=(
                "Public harvest requires a domain or email domain. "
                "Person-name seeds are covered by darkweb, sherlock, and breach_intel."
            ),
        )

    if not cli_args:
        cli_args = ["-d", domain, "-l", "100", "-b", "crtsh"]
    else:
        cli_args = list(cli_args)
        if "-d" in cli_args:
            idx = cli_args.index("-d")
            if idx + 1 < len(cli_args):
                cli_args[idx + 1] = _domain(str(cli_args[idx + 1]).replace("{{target}}", domain))
        else:
            cli_args = ["-d", domain, *cli_args]
        if "-b" in cli_args:
            idx = cli_args.index("-b")
            if idx + 1 < len(cli_args) and str(cli_args[idx + 1]).lower() in {
                "google",
                "bing",
                "yahoo",
            }:
                cli_args[idx + 1] = "crtsh"
        elif "--source" in cli_args:
            idx = cli_args.index("--source")
            if idx + 1 < len(cli_args) and str(cli_args[idx + 1]).lower() in {
                "google",
                "bing",
                "yahoo",
            }:
                cli_args[idx + 1] = "crtsh"

    cmd = [*_command(), *cli_args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        emails = sorted(
            {
                e
                for e in re.findall(r"[\w.+-]+@[\w.-]+\.\w+", output)
                if e.lower() not in _BANNER_EMAILS
            }
        )
        hosts = sorted(
            {
                h
                for h in re.findall(
                    rf"(?:[\w.-]+\.)?{re.escape(domain)}",
                    output,
                    flags=re.IGNORECASE,
                )
                if h.lower() != domain.lower()
            }
        )
        return {
            "tool": "theHarvester",
            "target": domain,
            "seeds": seeds,
            "emails": emails,
            "hosts": hosts,
            "raw_output": output,
            "productive": bool(emails or hosts),
        }
    except FileNotFoundError:
        return {
            "tool": "theHarvester",
            "target": domain,
            "seeds": seeds,
            "error": "theHarvester is not installed",
            "productive": False,
        }
    except subprocess.CalledProcessError as e:
        return {
            "tool": "theHarvester",
            "target": domain,
            "seeds": seeds,
            "error": str(e.output),
            "productive": False,
        }
