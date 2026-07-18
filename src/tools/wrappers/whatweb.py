import subprocess


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def scan(target, args=None):
    url = _url(target)
    if args is None:
        args = ["-a", "3"]
    cmd = ["whatweb", *args, url]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return {"tool": "whatweb", "target": url, "raw_output": output}
    except FileNotFoundError:
        return {"tool": "whatweb", "target": url, "error": "whatweb binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "whatweb", "target": url, "error": str(e.output)}
