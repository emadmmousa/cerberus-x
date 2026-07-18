import ipaddress
import shutil
import socket
import subprocess
from urllib.parse import urlparse

DEFAULT_TIMEOUT_SECONDS = 45
DEFAULT_PORTS = (80, 443, 22)


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def _resolve_ipv4(host: str) -> str:
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            return sockaddr[0]
    raise ValueError(f"Unable to resolve host: {host}")


def _ports_from_args(args: list[str]) -> list[int]:
    ports: list[int] = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("-p", "--target-port") and i + 1 < len(args):
            token = str(args[i + 1])
            for part in token.split(","):
                if part.strip().isdigit():
                    ports.append(int(part.strip()))
            skip_next = True
    return ports or list(DEFAULT_PORTS)


def _tcp_connect_ports(address: str, ports: list[int], timeout: float = 2.0) -> list[dict]:
    open_ports = []
    for port in ports:
        try:
            with socket.create_connection((address, port), timeout=timeout):
                open_ports.append({"ip": address, "port": str(port)})
        except OSError:
            continue
    return open_ports


def _run_zmap_port(address: str, port: int, timeout: int) -> tuple[str, bool]:
    # ZMap scans one port over a CIDR; /32 is the single-host case.
    cmd = [
        "zmap",
        "-p",
        str(port),
        "-o",
        "-",
        "-f",
        "saddr",
        "--cooldown-time=1",
        f"{address}/32",
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            start_new_session=True,
        )
    except FileNotFoundError:
        raise
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        return output, False
    output = (completed.stdout or "") + (completed.stderr or "")
    hit = any(line.strip() == address for line in (completed.stdout or "").splitlines())
    return output, hit


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    host = _host(target)
    try:
        address = _resolve_ipv4(host)
    except (ValueError, socket.gaierror) as exc:
        return {"tool": "zmap", "target": host, "error": str(exc)}

    args = list(args) if args is not None else ["-p", "80,443,22"]
    ports = _ports_from_args(args)
    if not shutil.which("zmap"):
        # Still useful in environments without the binary.
        fallback = _tcp_connect_ports(address, ports)
        return {
            "tool": "zmap",
            "target": host,
            "resolved": address,
            "open_ports": fallback,
            "method": "tcp-connect-fallback",
            "raw_output": "zmap binary not found; used TCP connect fallback",
        }

    outputs = []
    open_ports = []
    per_port_timeout = max(5, timeout // max(len(ports), 1))
    try:
        for port in ports:
            output, hit = _run_zmap_port(address, port, timeout=per_port_timeout)
            outputs.append(output)
            if hit:
                open_ports.append({"ip": address, "port": str(port)})
    except FileNotFoundError:
        open_ports = _tcp_connect_ports(address, ports)
        return {
            "tool": "zmap",
            "target": host,
            "resolved": address,
            "open_ports": open_ports,
            "method": "tcp-connect-fallback",
            "raw_output": "zmap binary not found; used TCP connect fallback",
        }

    method = "syn"
    if not open_ports:
        open_ports = _tcp_connect_ports(address, ports)
        method = "tcp-connect-fallback"
        outputs.append(
            "zmap SYN returned no hits; used TCP connect fallback "
            "(common under Docker Desktop networking)"
        )

    return {
        "tool": "zmap",
        "target": host,
        "resolved": address,
        "open_ports": open_ports,
        "method": method,
        "raw_output": "\n".join(chunk for chunk in outputs if chunk).strip(),
    }
