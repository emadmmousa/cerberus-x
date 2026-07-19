"""Upsert OXYLABS_PROXY_* keys in a dotenv-style file."""

from __future__ import annotations

from pathlib import Path

OXYLABS_KEYS = (
    "OXYLABS_PROXY_USERNAME",
    "OXYLABS_PROXY_PASSWORD",
    "OXYLABS_PROXY_HOST",
    "OXYLABS_PROXY_PORT",
    "OXYLABS_PROXY_PROTOCOL",
)


def upsert_oxylabs_keys(path: str, values: dict[str, str]) -> None:
    file_path = Path(path)
    if file_path.exists():
        lines = file_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []
        file_path.parent.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        if raw.lstrip().startswith("#") or "=" not in raw:
            out.append(raw)
            continue
        key, _, _rest = raw.partition("=")
        key = key.strip()
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(raw)

    for key in OXYLABS_KEYS:
        if key in values and key not in seen:
            out.append(f"{key}={values[key]}")

    content = "\n".join(out)
    if content and not content.endswith("\n"):
        content += "\n"
    elif not content:
        content = ""
    file_path.write_text(content, encoding="utf-8")


def clear_oxylabs_keys(path: str) -> None:
    upsert_oxylabs_keys(path, {key: "" for key in OXYLABS_KEYS})
