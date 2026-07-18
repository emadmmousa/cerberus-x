import subprocess
from urllib.parse import urlparse


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


def scan(target, args=None):
    host = _host(target)
    # -a requires the address value immediately after it.
    if args is None:
        args = ["-a", host, "--ulimit", "5000", "-g", "--no-banner"]
    else:
        args = list(args)
        if "-a" not in args and "--addresses" not in args:
            args = ["-a", host, *args]

    cmd = ["rustscan", *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ports = []
        for line in output.split("\n"):
            # greppable: "127.0.0.1 -> [80,443]"
            if "->" in line and "[" in line:
                bracket = line.split("[", 1)[1].split("]", 1)[0]
                for part in bracket.split(","):
                    port = part.strip()
                    if port.isdigit():
                        ports.append({"port": port, "state": "open"})
            elif "Open " in line:
                for part in line.split("Open ", 1)[1].replace(",", ".").split("."):
                    if part.strip().isdigit():
                        ports.append({"port": part.strip(), "state": "open"})
        return {
            "tool": "rustscan",
            "target": host,
            "ports": ports,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "rustscan", "target": host, "error": "rustscan binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "rustscan", "target": host, "error": str(e.output)}
