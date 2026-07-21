import ipaddress
import os
import re
import signal
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlparse

from tools.wrappers._argv import coerce_argv

# Hard ceiling so a broken wait-loop can never block the orchestrator.
DEFAULT_TIMEOUT_SECONDS = 45
# TCP-connect fallback must stay bounded (LLM plans often pass wide -p ranges).
MAX_FALLBACK_PORTS = 64
FALLBACK_BUDGET_SECONDS = 30
MAX_PORT_RANGE_SPAN = 256
_DONE_RE = re.compile(r"100\.00%\s+done", re.IGNORECASE)
_PORT_ARG_RE = re.compile(r"^-p(.+)$")
# Flags that belong to nmap / other scanners — masscan will hang or misparse them.
_FOREIGN_FLAGS = frozenset({"-sV", "-sS", "-sT", "-sU", "-A", "-O", "-Pn", "-n"})
_OUTPUT_FLAGS = frozenset(
    {"-oL", "-oJ", "-oX", "-oG", "-oN", "--output-format", "--output-filename"}
)


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


def _expand_port_token(token: str) -> list[int]:
    token = token.strip()
    if not token:
        return []
    if "-" in token:
        start_s, end_s = token.split("-", 1)
        if start_s.isdigit() and end_s.isdigit():
            start, end = int(start_s), int(end_s)
            if start > end or end - start > MAX_PORT_RANGE_SPAN:
                return []
            return list(range(start, end + 1))
        return []
    return [int(token)] if token.isdigit() else []


def sanitize_args(args: list[str] | None) -> list[str]:
    """Drop foreign/nmap flags and keep masscan invocations bounded."""
    if not args:
        return ["-p80,443,22,8080,8443", "--rate=1000", "--wait=0"]
    # Expand "--rate=1000 --wait=0" style glued LLM tokens first.
    expanded = coerce_argv(args)
    cleaned: list[str] = []
    skip_next = False
    for arg in expanded:
        if skip_next:
            skip_next = False
            continue
        if arg in _FOREIGN_FLAGS:
            continue
        if arg.startswith("-T") and len(arg) <= 3 and arg[2:].isdigit():
            continue
        if arg.startswith("--script"):
            if arg == "--script":
                skip_next = True
            continue
        if arg.startswith("--limit"):
            # masscan has no --limit; LLMs often copy nmap-ish forms
            if arg == "--limit":
                skip_next = True
            continue
        # We always force -oL ourselves; drop LLM invents like output=json / -oJ.
        if arg in _OUTPUT_FLAGS or arg.startswith("output="):
            if arg in _OUTPUT_FLAGS and "=" not in arg:
                skip_next = True
            continue
        if arg.startswith("-o") and len(arg) <= 3:
            skip_next = True
            continue
        # Strip rates here; re-add a clean numeric --rate below.
        if arg in {"--rate", "-rate"} or arg.startswith("--rate=") or arg.startswith(
            "-rate="
        ):
            if arg in {"--rate", "-rate"}:
                skip_next = True
            continue
        cleaned.append(arg)
    ports = _ports_from_args(cleaned)
    if not ports or len(ports) > MAX_FALLBACK_PORTS:
        # Replace unbounded/empty port specs with a safe common set.
        without_p: list[str] = []
        skip = False
        for arg in cleaned:
            if skip:
                skip = False
                continue
            if arg == "-p":
                skip = True
                continue
            if _PORT_ARG_RE.match(arg):
                continue
            without_p.append(arg)
        cleaned = [
            *without_p,
            f"-p{','.join(str(p) for p in (80, 443, 22, 8080, 8443))}",
        ]
    cleaned = _force_wait_zero(cleaned)
    return [*cleaned, "--rate=1000"]


def _ports_from_args(args: list[str]) -> list[int]:
    ports: list[int] = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == "-p" and i + 1 < len(args):
            for part in str(args[i + 1]).split(","):
                ports.extend(_expand_port_token(part))
            skip_next = True
            continue
        match = _PORT_ARG_RE.match(arg)
        if match:
            for part in match.group(1).split(","):
                ports.extend(_expand_port_token(part))
    # Deduplicate while preserving order.
    seen = set()
    unique = []
    for port in ports:
        if port not in seen:
            seen.add(port)
            unique.append(port)
    return unique


def _force_wait_zero(args: list[str]) -> list[str]:
    cleaned = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--wait":
            skip_next = True
            continue
        if arg.startswith("--wait="):
            continue
        cleaned.append(arg)
    return [*cleaned, "--wait=0"]


def _parse_ports(output: str) -> list[dict]:
    ports = []
    seen = set()
    for line in (output or "").splitlines():
        lower = line.lower()
        if "open port" not in lower and "discovered open port" not in lower:
            # list output: "open tcp 443 1.2.3.4 timestamps..."
            parts = line.split()
            if len(parts) >= 4 and parts[0] == "open" and parts[2].isdigit():
                key = (parts[2], parts[1])
                if key not in seen:
                    seen.add(key)
                    ports.append({"port": parts[2], "protocol": parts[1]})
            continue
        parts = line.replace("Discovered ", "").split()
        for part in parts:
            if "/" not in part:
                continue
            port, proto = part.split("/", 1)
            if port.isdigit():
                key = (port, proto)
                if key not in seen:
                    seen.add(key)
                    ports.append({"port": port, "protocol": proto})
    return ports


def _tcp_connect_ports(
    address: str,
    ports: list[int],
    timeout: float = 1.0,
    *,
    max_ports: int = MAX_FALLBACK_PORTS,
    budget_seconds: float = FALLBACK_BUDGET_SECONDS,
) -> list[dict]:
    open_ports = []
    deadline = time.monotonic() + budget_seconds
    for port in ports[:max_ports]:
        if time.monotonic() >= deadline:
            break
        try:
            with socket.create_connection((address, port), timeout=timeout):
                open_ports.append({"port": str(port), "protocol": "tcp"})
        except OSError:
            continue
    return open_ports


def _kill_process_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def _run_masscan_syn(
    address: str, args: list[str], timeout: int
) -> tuple[str, list[dict]]:
    """
    Run masscan and guarantee exit.

    Docker Desktop often leaves masscan stuck after '100.00% done' in the wait
    loop. We watch for completion, then force-kill if it does not exit.
    """
    args = _force_wait_zero(list(args))
    with tempfile.NamedTemporaryFile(prefix="masscan-", suffix=".list", delete=False) as handle:
        list_path = handle.name

    cmd = ["masscan", *args, "-oL", list_path, address]
    output_chunks: list[str] = []
    done_at: float | None = None
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
        bufsize=1,
    )

    deadline = time.monotonic() + timeout
    try:
        assert proc.stdout is not None
        while True:
            if time.monotonic() > deadline:
                break
            line = proc.stdout.readline()
            if line:
                output_chunks.append(line)
                if _DONE_RE.search(line) and done_at is None:
                    # Allow a brief drain window, then stop waiting forever.
                    done_at = time.monotonic()
            elif proc.poll() is not None:
                break
            else:
                time.sleep(0.05)

            if done_at is not None and time.monotonic() - done_at >= 1.5:
                break

            if proc.poll() is not None:
                rest = proc.stdout.read()
                if rest:
                    output_chunks.append(rest)
                break
    finally:
        _kill_process_group(proc)
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc)

    list_text = ""
    try:
        with open(list_path, encoding="utf-8", errors="replace") as handle:
            list_text = handle.read()
    except OSError:
        list_text = ""
    finally:
        try:
            os.unlink(list_path)
        except OSError:
            pass

    combined = "".join(output_chunks)
    if list_text:
        combined = f"{combined}\n{list_text}" if combined else list_text
    return combined, _parse_ports(combined)


def scan(target, args=None, timeout: int = DEFAULT_TIMEOUT_SECONDS):
    args = sanitize_args(list(args) if args is not None else None)

    host = _extract_host(target)
    try:
        address = _resolve_target(host)
    except ValueError as exc:
        return {"tool": "masscan", "target": host, "error": str(exc)}

    requested_ports = _ports_from_args(args) or [80, 443, 22]

    try:
        syn_output, syn_ports = _run_masscan_syn(address, args, timeout=timeout)
    except FileNotFoundError:
        return {"tool": "masscan", "target": host, "error": "masscan binary not found"}

    if syn_ports:
        return {
            "tool": "masscan",
            "target": host,
            "resolved": address,
            "ports": syn_ports,
            "method": "syn",
            "raw_output": syn_output,
        }

    # Docker Desktop frequently drops/blackholes masscan SYN replies.
    # Fall back to TCP connect against the requested ports so scans stay useful.
    fallback_ports = _tcp_connect_ports(address, requested_ports)
    note = (
        "masscan SYN returned no open ports; "
        "used TCP connect fallback (common under Docker Desktop networking)"
    )
    raw = f"{syn_output.rstrip()}\n{note}".strip()
    return {
        "tool": "masscan",
        "target": host,
        "resolved": address,
        "ports": fallback_ports,
        "method": "tcp-connect-fallback",
        "raw_output": raw,
    }
