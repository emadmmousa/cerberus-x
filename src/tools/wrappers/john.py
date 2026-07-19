import os
import subprocess
from urllib.parse import urlparse


def _looks_like_url(value: str) -> bool:
    return "://" in value or (
        "." in value and "/" not in value and not os.path.exists(value)
    )


def scan(target, args=None):
    # John needs a local hash file. URLs/hostnames are skipped, not treated as errors.
    if _looks_like_url(target) or not os.path.exists(target):
        return {
            "tool": "john",
            "target": target,
            "cracked": [],
            "skipped": True,
            "raw_output": "No local hash file provided; john was skipped",
        }

    if args is None:
        wordlist = "/usr/share/john/password.lst"
        if not os.path.isfile(wordlist):
            wordlist = "/usr/share/wordlists/rockyou.txt"
        args = [f"--wordlist={wordlist}", "--format=nt"]

    cmd = ["john", *args, target]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        cracked = []
        for line in output.split("\n"):
            if "(" in line and ")" in line and "password" not in line.lower():
                parts = line.split("(")
                if len(parts) == 2:
                    cracked.append(
                        {
                            "username": parts[1].replace(")", "").strip(),
                            "password": parts[0].strip(),
                        }
                    )
        return {
            "tool": "john",
            "target": target,
            "cracked": cracked,
            "raw_output": output,
        }
    except FileNotFoundError:
        return {"tool": "john", "target": target, "error": "john binary not found"}
    except subprocess.CalledProcessError as e:
        return {"tool": "john", "target": target, "error": str(e.output)}
