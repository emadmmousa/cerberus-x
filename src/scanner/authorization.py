"""Authorization gate for active scanning APIs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flask import request

from security.audit import audit_log


def _normalize_host(target: str) -> str:
    value = (target or "").strip()
    if "://" not in value:
        value = f"https://{value}"
    host = (urlparse(value).hostname or "").lower().strip(".")
    return host


def _entry_active(item: dict) -> bool:
    """Honor optional authorized flag + expiry on a target entry."""
    if "authorized" in item and not item.get("authorized"):
        return False
    expiry = item.get("expiry")
    if expiry:
        try:
            if datetime.fromisoformat(str(expiry)) < datetime.now():
                return False
        except ValueError:
            pass
    return True


def targets_file_path() -> Path:
    return Path(
        os.getenv(
            "AUTHORIZED_TARGETS_FILE",
            str(Path(__file__).resolve().parents[2] / "authorized_targets.json"),
        )
    )


def load_targets_document() -> dict:
    path = targets_file_path()
    if not path.is_file():
        return {"targets": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"targets": []}
    if isinstance(data, list):
        return {"targets": data}
    if isinstance(data, dict):
        items = data.get("targets") or data.get("hosts") or []
        return {"targets": list(items) if isinstance(items, list) else []}
    return {"targets": []}


def save_targets_document(doc: dict) -> None:
    path = targets_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"targets": doc.get("targets") or []}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _entry_host(item: dict | str) -> str:
    if isinstance(item, dict):
        raw = str(item.get("target") or item.get("host") or item.get("url") or "")
    else:
        raw = str(item)
    return _normalize_host(raw)


def _same_scope_host(left: str, right: str) -> bool:
    if not left or not right:
        return False
    a = left[4:] if left.startswith("www.") else left
    b = right[4:] if right.startswith("www.") else right
    return a == b


def list_target_entries(*, active_only: bool = False) -> list[dict]:
    doc = load_targets_document()
    rows: list[dict] = []
    for item in doc.get("targets") or []:
        if isinstance(item, dict):
            if active_only and not _entry_active(item):
                continue
            host = _entry_host(item)
            rows.append(
                {
                    "target": host or str(item.get("target") or item.get("host") or ""),
                    "host": host,
                    "authorized": item.get("authorized", True),
                    "expiry": item.get("expiry"),
                    "notes": item.get("notes") or item.get("note"),
                    "added_at": item.get("added_at"),
                }
            )
        else:
            host = _normalize_host(str(item))
            if host:
                rows.append(
                    {
                        "target": host,
                        "host": host,
                        "authorized": True,
                        "expiry": None,
                        "notes": None,
                        "added_at": None,
                    }
                )
    return rows


def add_target_entry(
    target: str,
    *,
    notes: str | None = None,
    expiry: str | None = None,
    authorized: bool = True,
) -> dict:
    host = _normalize_host(target)
    if not host:
        raise ValueError("invalid target")
    doc = load_targets_document()
    items: list = list(doc.get("targets") or [])
    for index, item in enumerate(items):
        existing = _entry_host(item) if isinstance(item, (dict, str)) else ""
        if _same_scope_host(existing, host):
            merged = dict(item) if isinstance(item, dict) else {"target": existing}
            merged["target"] = host
            merged["authorized"] = authorized
            if notes is not None:
                merged["notes"] = notes
            if expiry is not None:
                merged["expiry"] = expiry
            items[index] = merged
            save_targets_document({"targets": items})
            audit_log("AUTHZ_TARGET_UPDATED", {"target": host, "authorized": authorized})
            return merged

    entry = {
        "target": host,
        "authorized": authorized,
        "added_at": datetime.now().isoformat(timespec="seconds"),
    }
    if notes:
        entry["notes"] = notes
    if expiry:
        entry["expiry"] = expiry
    items.append(entry)
    save_targets_document({"targets": items})
    audit_log("AUTHZ_TARGET_ADDED", {"target": host, "authorized": authorized})
    return entry


def remove_target_entry(target: str) -> bool:
    host = _normalize_host(target)
    if not host:
        raise ValueError("invalid target")
    doc = load_targets_document()
    items: list = list(doc.get("targets") or [])
    kept: list = []
    removed = False
    for item in items:
        existing = _entry_host(item) if isinstance(item, (dict, str)) else ""
        if _same_scope_host(existing, host):
            removed = True
            continue
        kept.append(item)
    if removed:
        save_targets_document({"targets": kept})
        audit_log("AUTHZ_TARGET_REMOVED", {"target": host})
    return removed


class AuthorizationEnforcer:
    """
    Default: allow scans (authorized engagements) and audit them.
    Set FIREBREAK_REQUIRE_AUTHZ=true and populate authorized_targets.json to enforce.
    """

    @staticmethod
    def _authorized_hosts() -> set[str]:
        path = targets_file_path()
        if not path.is_file():
            return set()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        hosts: set[str] = set()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("targets") or data.get("hosts") or []
        else:
            items = []
        for item in items:
            # Support both plain strings and {"target"/"host"/"url": ..., ...} objects.
            if isinstance(item, dict):
                if not _entry_active(item):
                    continue
                raw = str(
                    item.get("target") or item.get("host") or item.get("url") or ""
                )
            else:
                raw = str(item)
            host = _normalize_host(raw)
            if host:
                hosts.add(host)
                if host.startswith("www."):
                    hosts.add(host[4:])
                else:
                    hosts.add(f"www.{host}")
        return hosts

    @staticmethod
    def check(target: str) -> bool:
        require = os.getenv("FIREBREAK_REQUIRE_AUTHZ", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not require:
            return True
        host = _normalize_host(target)
        allowed = AuthorizationEnforcer._authorized_hosts()
        return bool(host and host in allowed)

    @staticmethod
    def before_request():
        if request.path.startswith("/api/scan") and request.method == "POST":
            data = request.get_json(silent=True) or {}
            target = data.get("target")
            if target:
                audit_log(
                    "SCAN_AUTHZ_CHECK",
                    {
                        "target": target,
                        "allowed": AuthorizationEnforcer.check(target),
                        "path": request.path,
                    },
                )
        return None
