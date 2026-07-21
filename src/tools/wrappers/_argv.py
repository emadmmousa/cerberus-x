"""Shared argv cleaning for tool wrappers (LLM often glues flags into one token)."""

from __future__ import annotations

import re
import shlex
from typing import Iterable, List, Sequence

_GLUED_FLAG = re.compile(r"^-[A-Za-z0-9][\w-]*(?:\s+|$)")
_HTTP_REQUEST_LINE = re.compile(
    r"^(GET|POST|PUT|HEAD|OPTIONS|DELETE|PATCH)\s+\S+\s+HTTP/\d",
    re.IGNORECASE,
)


def coerce_argv(args: Sequence | None) -> List[str]:
    """Normalize playbook/LLM args into a flat argv list of strings."""
    if args is None:
        return []
    if isinstance(args, str):
        return _split_token(args)
    if isinstance(args, dict):
        # {"-p": "80,443"} style — uncommon but seen from LLMs
        out: list[str] = []
        for key, value in args.items():
            k = str(key)
            if not k.startswith("-"):
                k = f"-{k}"
            out.append(k)
            if value is not None and value != "":
                out.extend(_split_token(str(value)))
        return expand_glued_argv(out)
    out: list[str] = []
    for item in args:
        if item is None:
            continue
        if isinstance(item, (list, tuple)):
            out.extend(coerce_argv(item))
        else:
            out.extend(_split_token(str(item)))
    return expand_glued_argv(out)


def _split_token(token: str) -> List[str]:
    text = token.strip()
    if not text:
        return []
    # Already a single clean flag or value
    if " " not in text and "\t" not in text:
        return [text]
    # Prefer shell-like split for quoted fragments
    try:
        parts = shlex.split(text, posix=True)
        if parts:
            return parts
    except ValueError:
        pass
    return text.split()


def expand_glued_argv(args: Iterable[str]) -> List[str]:
    """
    Expand tokens like '-w /tmp/w.txt http://x HTTP/1.1' that LLMs emit as one argv.
    Drops HTTP request-line junk that is not a valid flag/value.
    """
    out: list[str] = []
    for raw in args:
        token = str(raw).strip()
        if not token:
            continue
        if _HTTP_REQUEST_LINE.match(token):
            continue
        # Split long-option glue: "--rate=1000 --wait=0" (common LLM mistake).
        if " --" in token and token.startswith("-"):
            out.extend(_split_token(token))
            continue
        if " " in token and _GLUED_FLAG.match(token):
            out.extend(_split_token(token))
            continue
        # Bare request-line fragments without leading method glued after a path
        if " HTTP/1." in token or " HTTP/2" in token:
            # Keep path-like prefix before HTTP/ if it looks like a wordlist path
            before = token.split(" HTTP/", 1)[0].strip()
            if before.startswith("/") or before.endswith(".txt"):
                out.append(before)
            continue
        out.append(token)
    return out


def drop_unknown_flags(
    args: Sequence[str],
    *,
    allowed_flags: set[str],
    value_flags: set[str] | None = None,
) -> List[str]:
    """Keep only allowlisted flags (and their values). Non-flag tokens kept as-is."""
    value_flags = value_flags or set()
    out: list[str] = []
    skip_next = False
    for index, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("-"):
            # --flag=value
            base = arg.split("=", 1)[0]
            if base not in allowed_flags and arg not in allowed_flags:
                # skip optional value
                if arg in value_flags or base in value_flags:
                    if index + 1 < len(args) and not str(args[index + 1]).startswith("-"):
                        skip_next = True
                continue
            out.append(arg)
            if "=" not in arg and (arg in value_flags or base in value_flags):
                if index + 1 < len(args) and not str(args[index + 1]).startswith("-"):
                    out.append(str(args[index + 1]))
                    skip_next = True
            continue
        out.append(arg)
    return out
