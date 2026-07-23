"""Unicode helpers — repair common UTF-8 / Latin-1 mojibake."""

from __future__ import annotations

import re

_MOJIBAKE_MARKERS = re.compile(r"[ØÙÃâ�]")
_C1_MOJIBAKE = re.compile(r"[\u0080-\u009f]")


def looks_mojibake(text: str) -> bool:
    if not text:
        return False
    return bool(_MOJIBAKE_MARKERS.search(text) or _C1_MOJIBAKE.search(text))


def repair_mojibake(text: str) -> str:
    """Recover UTF-8 text that was mis-decoded as Latin-1 or CP1252."""
    if not text or not looks_mojibake(text):
        return text
    best = text
    for encoding in ("latin-1", "cp1252"):
        try:
            candidate = text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if candidate and _quality(candidate) >= _quality(best):
            best = candidate
    return best


def ensure_utf8_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text or "")
    return repair_mojibake(text)


def _quality(text: str) -> tuple[int, int]:
    """Prefer fewer mojibake markers and more non-ASCII letters when tied."""
    bad = len(_MOJIBAKE_MARKERS.findall(text)) + len(_C1_MOJIBAKE.findall(text))
    letters = sum(1 for ch in text if ch.isalpha() and ord(ch) > 127)
    return (-bad, letters)
