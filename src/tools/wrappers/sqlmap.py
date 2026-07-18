import subprocess


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def scan(target, args=None):
    url = _url(target)
    if args is None:
        args = ["--batch", "--level=2"]
    cmd = ["sqlmap", "-u", url, *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        vulnerable = "vulnerable" in output.lower() or "sql injection" in output.lower()
        return {
            "tool": "sqlmap",
            "target": url,
            "vulnerable": vulnerable,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "sqlmap", "target": url, "error": "sqlmap binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "sqlmap", "target": url, "error": str(e.output)}
