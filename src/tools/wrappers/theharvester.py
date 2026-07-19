import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse


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
    domain = _domain(target)
    if args is None:
        args = ["-d", domain, "-l", "100", "-b", "crtsh"]
    else:
        args = list(args)
        # Ensure -d gets a cleaned domain if playbook passed a URL.
        if "-d" in args:
            idx = args.index("-d")
            if idx + 1 < len(args):
                args[idx + 1] = _domain(str(args[idx + 1]).replace("{{target}}", domain))
        else:
            args = ["-d", domain, *args]
        if "-b" in args:
            idx = args.index("-b")
            if idx + 1 < len(args) and str(args[idx + 1]).lower() in {
                "google",
                "bing",
                "yahoo",
            }:
                args[idx + 1] = "crtsh"
        elif "--source" in args:
            idx = args.index("--source")
            if idx + 1 < len(args) and str(args[idx + 1]).lower() in {
                "google",
                "bing",
                "yahoo",
            }:
                args[idx + 1] = "crtsh"

    cmd = [*_command(), *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        emails = sorted(set(re.findall(r"[\w.+-]+@[\w.-]+\.\w+", output)))
        hosts = sorted(
            set(
                re.findall(
                    rf"(?:[\w.-]+\.)?{re.escape(domain)}",
                    output,
                    flags=re.IGNORECASE,
                )
            )
        )
        return {
            "tool": "theHarvester",
            "target": domain,
            "emails": emails,
            "hosts": hosts,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {
            "tool": "theHarvester",
            "target": domain,
            "error": "theHarvester is not installed",
        }
    except subprocess.CalledProcessError as e:
        return {"tool": "theHarvester", "target": domain, "error": str(e.output)}
