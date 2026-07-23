"""Resolve web content wordlists to paths that exist on the worker."""

from __future__ import annotations

import os

DEFAULT_WORDLIST = "/usr/share/dirb/wordlists/common.txt"

# LLM/playbook paths that are commonly cited but absent from slim Docker images.
WORDLIST_ALIASES: dict[str, str] = {
    "/usr/share/wordlists/dirb/common.txt": DEFAULT_WORDLIST,
    "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt": DEFAULT_WORDLIST,
    "/usr/share/seclists/Discovery/Web-Content/common.txt": DEFAULT_WORDLIST,
    "/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt": DEFAULT_WORDLIST,
    "/usr/share/seclists/Discovery/Web-Content/raft-medium-words.txt": DEFAULT_WORDLIST,
    "/usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt": DEFAULT_WORDLIST,
    "common.txt": DEFAULT_WORDLIST,
}

WORDLIST_CANDIDATES: tuple[str, ...] = (
    DEFAULT_WORDLIST,
    "/usr/share/dirb/wordlists/small.txt",
    "/usr/share/wordlists/dirb/common.txt",
    "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
)

_EPHEMERAL = "/tmp/firebreak-dir-words.txt"
_FALLBACK_LINES = ("admin\nlogin\napi\nrobots.txt\n.git\nwp-admin\nwp-login.php\n")


def _write_ephemeral_wordlist() -> str | None:
    try:
        with open(_EPHEMERAL, "w", encoding="utf-8") as handle:
            handle.write(_FALLBACK_LINES)
        return _EPHEMERAL
    except OSError:
        return None


def resolve_wordlist(path: str | None = None) -> str:
    """Return a wordlist path guaranteed to exist, or raise FileNotFoundError."""
    if path:
        cleaned = str(path).strip().split()[0].split("HTTP/")[0].strip()
        if cleaned:
            candidate = WORDLIST_ALIASES.get(cleaned, cleaned)
            if os.path.isfile(candidate):
                return candidate

    for candidate in WORDLIST_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate

    ephemeral = _write_ephemeral_wordlist()
    if ephemeral:
        return ephemeral

    raise FileNotFoundError(
        "no web content wordlist found (install dirb or set -w to a valid path)"
    )


def rewrite_wordlist_arg(args: list[str]) -> list[str]:
    """Replace -w/--wordlist values with a path that exists on this worker."""
    out: list[str] = []
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in {"-w", "--wordlist"} and index + 1 < len(args):
            resolved = resolve_wordlist(args[index + 1])
            out.extend([arg, resolved])
            skip_next = True
            continue
        if isinstance(arg, str) and arg.startswith("-w="):
            resolved = resolve_wordlist(arg.split("=", 1)[1])
            out.append(f"-w={resolved}")
            continue
        if isinstance(arg, str) and arg.startswith("--wordlist="):
            resolved = resolve_wordlist(arg.split("=", 1)[1])
            out.append(f"--wordlist={resolved}")
            continue
        out.append(arg)
    return out
