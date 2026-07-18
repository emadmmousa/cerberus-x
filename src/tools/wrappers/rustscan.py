import subprocess
from urllib.parse import urlparse


def _host(target: str) -> str:
    parsed = urlparse(target if "://" in target else f"//{target}", scheme="")
    host = parsed.hostname or parsed.path.split("/")[0] or target
    return host.strip("[]")


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
        args = list(args)
        if "-a" not in args and "--addresses" not in args:
            args = ["-a", host, *args]
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
