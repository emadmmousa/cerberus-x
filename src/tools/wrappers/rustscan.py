import re
import subprocess
from urllib.parse import urlparse

_OPEN_HOST_PORT_RE = re.compile(
    r"Open\s+(?:\[[^\]]+\]|[\w.-]+):(\d+)\b",
    re.IGNORECASE,
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _ensure_address(args: list[str], host: str) -> list[str]:
    """Ensure `-a/--addresses` is present and followed by a host value."""
    normalized = list(args)

    def _needs_value(flag: str) -> bool:
        if flag not in normalized:
            return False
        idx = normalized.index(flag)
        return idx + 1 >= len(normalized) or str(normalized[idx + 1]).startswith("-")

    if _needs_value("-a"):
        idx = normalized.index("-a")
        normalized.insert(idx + 1, host)
    elif _needs_value("--addresses"):
        idx = normalized.index("--addresses")
        normalized.insert(idx + 1, host)
    elif "-a" not in normalized and "--addresses" not in normalized:
        normalized = ["-a", host, *normalized]
    return normalized


def _ensure_quiet_flags(args: list[str]) -> list[str]:
    normalized = list(args)
    if "-g" not in normalized and "--greppable" not in normalized:
        normalized.append("-g")
    if "--no-banner" not in normalized:
        normalized.append("--no-banner")
    return normalized


def _parse_ports(output: str) -> list[dict]:
    ports: list[dict] = []
    seen: set[str] = set()
    clean = _ANSI_RE.sub("", output or "")
    for line in clean.splitlines():
        text = line.strip()
        if "->" in text and "[" in text:
            bracket = text.split("[", 1)[1].split("]", 1)[0]
            candidates = [part.strip() for part in bracket.split(",")]
        else:
            candidates = _OPEN_HOST_PORT_RE.findall(text)
        for port in candidates:
            if port.isdigit() and port not in seen:
                seen.add(port)
                ports.append({"port": port, "state": "open"})
    return ports


def scan(target, args=None):
    host = _host(target)
    # Rustscan 2.x: -p is comma ports, -r is ranges, --top is top 1000.
    # -a must be followed immediately by the address value.
    if args is None:
        args = [
            "-a",
            host,
            "--ulimit",
            "5000",
            "--top",
            "-g",
            "--no-banner",
            "-t",
            "3000",
        ]
    else:
        args = _ensure_quiet_flags(_ensure_address(list(args), host))
        if (
            "-p" not in args
            and "--ports" not in args
            and "-r" not in args
            and "--range" not in args
            and "--top" not in args
        ):
            args = [*args, "--top"]

    cmd = ["rustscan", *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ports = _parse_ports(output)
        result = {
            "tool": "rustscan",
            "target": host,
            "ports": ports,
            "raw_output": output,
        }
        if not ports and not output.strip():
            result["raw_output"] = (
                "rustscan completed with no open ports "
                "(SYN scan may be filtered; try nmap)"
            )
        return result
    except FileNotFoundError:
        return {"tool": "rustscan", "target": host, "error": "rustscan binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "rustscan", "target": host, "error": str(e.output)}
