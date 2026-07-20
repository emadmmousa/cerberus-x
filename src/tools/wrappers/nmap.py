import re
import subprocess
from urllib.parse import urlparse

from tools.wrappers._argv import coerce_argv

_DEFAULT_PORTS = "21,22,80,443,8080,8443,3389"
_PORT_SPEC_RE = re.compile(r"^[0-9,\-T:U]+$", re.IGNORECASE)


def _host(target):
    """nmap expects a host/IP, not a full URL."""
    if "://" in target:
        return urlparse(target).hostname or target
    return target.split("/")[0] or target


def sanitize_args(args: list | None) -> list[str]:
    """Fix LLM-invented illegal -p specs and glued argv tokens."""
    args = coerce_argv(args)
    if not args:
        return ["-sV", f"-p{_DEFAULT_PORTS}", "-T4"]

    out: list[str] = []
    skip_next = False
    has_ports = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        # Drop accidental bare URLs (host is appended by scan()).
        if "://" in arg:
            continue

        if arg in {"-p", "--ports"}:
            value = args[index + 1] if index + 1 < len(args) else ""
            skip_next = index + 1 < len(args)
            cleaned = _clean_port_spec(str(value))
            out.extend(["-p", cleaned])
            has_ports = True
            continue
        if arg.startswith("-p") and arg not in {
            "-Pn",
            "-PE",
            "-PP",
            "-PM",
            "-PS",
            "-PA",
            "-PU",
            "-PY",
        }:
            spec = arg[2:]
            if spec.startswith("="):
                spec = spec[1:]
            cleaned = _clean_port_spec(spec)
            out.append(f"-p{cleaned}")
            has_ports = True
            continue
        out.append(arg)

    if not has_ports and "-F" not in out and "--top-ports" not in out:
        out.extend(["-p", _DEFAULT_PORTS])
    if not any(a.startswith("-T") for a in out):
        out.append("-T4")
    if "-sV" not in out and "-sC" not in out:
        out.insert(0, "-sV")
    return out


def _clean_port_spec(spec: str) -> str:
    text = (spec or "").strip().strip("\"'")
    text = text.replace(" ", "")
    # Strip accidental URL / host debris
    text = re.sub(r"https?://[^,]*", "", text, flags=re.IGNORECASE)
    text = text.strip(",/")
    if not text or not _PORT_SPEC_RE.match(text):
        return _DEFAULT_PORTS
    # Disallow empty ranges like "80,-" or leading commas
    if text.startswith(",") or text.endswith(",") or ",," in text:
        return _DEFAULT_PORTS
    return text


def scan(target, args=None):
    host = _host(target)
    args = sanitize_args(list(args) if args is not None else None)
    cmd = ["nmap", *args, host]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ports = []
        for line in output.split("\n"):
            if "/tcp" in line or "/udp" in line:
                parts = line.split()
                if len(parts) >= 3:
                    port = parts[0].split("/")[0]
                    state = parts[1]
                    service = " ".join(parts[2:])
                    ports.append({"port": port, "state": state, "service": service})
        return {
            "tool": "nmap",
            "target": target,
            "ports": ports,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "nmap", "target": target, "error": "nmap binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "nmap", "target": target, "error": str(e.output)}
