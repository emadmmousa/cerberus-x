import re
import subprocess


def _url(target: str) -> str:
    if "://" in target:
        return target
    return f"https://{target}"


def scan(target, args=None):
    url = _url(target)
    if args is None:
        args = [
            "-t",
            "/root/nuclei-templates/http/cves/",
            "-severity",
            "critical,high",
            "-silent",
        ]
    else:
        args = list(args)

    cmd = ["nuclei", "-u", url, *args]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return {"tool": "nuclei", "target": url, "error": "nuclei binary not found"}
    except subprocess.CalledProcessError as e:
        output = e.output or ""
        if not output:
            return {"tool": "nuclei", "target": url, "error": str(e)}

    findings = []
    for line in output.split("\n"):
        if "[" not in line or "]" not in line:
            continue
        match = re.search(r"\[(.*?)\]\s*(.*?)(?:\s+\[(.*?)\])?", line)
        if match:
            findings.append({"severity": match.group(1), "title": match.group(2)})
    return {
        "tool": "nuclei",
        "target": url,
        "findings": findings,
        "raw_output": output if output.strip() else "no findings",
    }
