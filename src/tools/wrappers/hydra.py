import subprocess
from urllib.parse import urlparse


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def scan(target, args=None):
    host = _host(target)
    if not args:
        return {
            "tool": "hydra",
            "target": host,
            "error": "hydra requires an explicit service and arguments",
        }

    service, *options = list(args)
    if not isinstance(service, str) or not service or service.startswith("-"):
        return {
            "tool": "hydra",
            "target": host,
            "error": "the first Hydra argument must be a service name",
        }

    command = ["hydra", *options, host, service]
    try:
        output = subprocess.check_output(
            command,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return {
            "tool": "hydra",
            "target": host,
            "service": service,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {
            "tool": "hydra",
            "target": host,
            "service": service,
            "error": "hydra binary not found",
        }
    except subprocess.CalledProcessError as exc:
        return {
            "tool": "hydra",
            "target": host,
            "service": service,
            "error": str(exc.output or exc),
        }
