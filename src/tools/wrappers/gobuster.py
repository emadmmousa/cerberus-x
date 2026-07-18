import subprocess
from urllib.parse import urlparse

WORDLIST = "/usr/share/dirb/wordlists/common.txt"


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def scan(target, args=None):
    url = _url(target)
    if args is None:
        args = ["dir", "-u", url, "-w", WORDLIST, "-q", "-t", "20"]
    else:
        args = [
            arg.replace("{{target}}", url) if isinstance(arg, str) else arg
            for arg in args
        ]

    cmd = ["gobuster", *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        directories = []
        for line in output.split("\n"):
            if "Status:" not in line and "(Status:" not in line:
                continue
            parts = line.split()
            if not parts:
                continue
            path = parts[0]
            status = None
            for part in parts:
                if part.startswith("(Status:") or part.startswith("Status:"):
                    status = part.split(":", 1)[1].rstrip(")")
            if status:
                directories.append({"path": path, "status": status})
        return {
            "tool": "gobuster",
            "target": url,
            "directories": directories,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "gobuster", "target": url, "error": "gobuster binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "gobuster", "target": url, "error": str(e.output)}
