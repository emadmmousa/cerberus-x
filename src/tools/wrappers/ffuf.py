import subprocess

WORDLIST = "/usr/share/dirb/wordlists/common.txt"


def _url(target: str) -> str:
    if "://" in target:
        return target.rstrip("/")
    return f"https://{target}".rstrip("/")


def scan(target, args=None):
    url = _url(target)
    if args is None:
        args = [
            "-u",
            f"{url}/FUZZ",
            "-w",
            WORDLIST,
            "-mc",
            "200,204,301,302,307,401,403",
            "-t",
            "20",
            "-maxtime",
            "60",
        ]
    else:
        args = [
            arg.replace("{{target}}", url) if isinstance(arg, str) else arg
            for arg in args
        ]

    cmd = ["ffuf", *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        results = []
        for line in output.split("\n"):
            if "Status:" not in line:
                continue
            status = None
            size = None
            path = None
            for part in line.replace(",", " ").split():
                if part.startswith("Status:"):
                    status = part.split(":", 1)[1]
                elif part.startswith("Size:"):
                    size = part.split(":", 1)[1]
                elif path is None and part and not part.startswith("["):
                    path = part
            if path and status:
                results.append({"path": path, "status": status, "size": size})
        return {
            "tool": "ffuf",
            "target": url,
            "results": results,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "ffuf", "target": url, "error": "ffuf binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "ffuf", "target": url, "error": str(e.output)}
