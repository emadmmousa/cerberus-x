import ipaddress
import socket
import subprocess
from urllib.parse import urlparse


def _extract_host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _resolve_target(host: str) -> str:
    """Masscan accepts only IPs/CIDR, not DNS names."""
    try:
        ipaddress.ip_network(host, strict=False)
        return host
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve host: {host}") from exc

    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            return sockaddr[0]
    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET6:
            return sockaddr[0]
    raise ValueError(f"Unable to resolve host: {host}")


def scan(target, args=None):
    if args is None:
        args = ["-p1-65535", "--rate=1000", "--wait=0"]

    host = _extract_host(target)
    try:
        address = _resolve_target(host)
    except ValueError as exc:
        return {"tool": "masscan", "target": host, "error": str(exc)}

    cmd = ["masscan"] + list(args) + [address]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ports = []
        for line in output.split("\n"):
            if "open port" not in line:
                continue
            parts = line.split()
            for part in parts:
                if "/" not in part:
                    continue
                port, proto = part.split("/", 1)
                if port.isdigit():
                    ports.append({"port": port, "protocol": proto})
        return {
            "tool": "masscan",
            "target": host,
            "resolved": address,
            "ports": ports,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "masscan", "target": host, "error": "masscan binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "masscan", "target": host, "error": str(e.output)}
