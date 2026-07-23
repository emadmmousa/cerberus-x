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
    override = os.getenv("AUTHORIZED_TARGETS_FILE")
    if override:
        return Path(override)
    output_dir = os.getenv("FIREBREAK_OUTPUT_DIR")
    if output_dir:
        return Path(output_dir) / "authorized_targets.json"
    return Path(__file__).resolve().parents[2] / "authorized_targets.json"


def _ensure_targets_file(path: Path) -> None:
    """Create the targets file on first use (seed from example/legacy if present)."""
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[2]
    seed_from = os.getenv("AUTHORIZED_TARGETS_SEED", "").strip()
    candidates = [
        Path(seed_from) if seed_from else None,
        Path("/app/authorized_targets.json"),
        repo_root / "authorized_targets.json",
        repo_root / "authorized_targets.example.json",
    ]
    for src in candidates:
        if src and src.is_file():
            try:
                path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                return
            except OSError:
                continue
    path.write_text(json.dumps({"targets": []}, indent=2) + "\n", encoding="utf-8")


def load_targets_document() -> dict:
    path = targets_file_path()
    _ensure_targets_file(path)
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
    _ensure_targets_file(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"targets": doc.get("targets") or []}
    try:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise PermissionError(
            f"cannot write authorized targets to {path}: {exc}. "
            "Set AUTHORIZED_TARGETS_FILE to a writable path "
            "(e.g. /app/output/authorized_targets.json in Docker)."
        ) from exc


def _entry_host(item: dict | str) -> str:
    if isinstance(item, dict):
        kind = str(item.get("kind") or "domain").strip().lower()
        if kind != "domain":
            return str(item.get("value") or item.get("target") or item.get("host") or "").strip()
        raw = str(item.get("target") or item.get("host") or item.get("url") or "")
    else:
        raw = str(item)
    return _normalize_host(raw)


def _entry_seed(item: dict | str) -> dict[str, str] | None:
    if isinstance(item, dict):
        raw = str(item.get("value") or item.get("target") or item.get("host") or item.get("url") or "")
        kind = str(item.get("kind") or "").strip().lower() or None
    else:
        raw = str(item)
        kind = None
    raw = raw.strip()
    if not raw:
        return None
    try:
        from orchestrator.osint.seeds import classify_osint_seed

        return classify_osint_seed(raw, kind=kind)
    except ValueError:
        host = _normalize_host(raw)
        if host:
            return {"kind": "domain", "value": host, "display": host}
        return None


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
            seed = _entry_seed(item)
            rows.append(
                {
                    "target": (seed or {}).get("display") or host or str(item.get("target") or item.get("host") or ""),
                    "host": host,
                    "kind": (seed or {}).get("kind") or "domain",
                    "value": (seed or {}).get("value") or host,
                    "authorized": item.get("authorized", True),
                    "expiry": item.get("expiry"),
                    "notes": item.get("notes") or item.get("note"),
                    "added_at": item.get("added_at"),
                }
            )
        else:
            seed = _entry_seed(item)
            host = _entry_host(item)
            if host or seed:
                rows.append(
                    {
                        "target": (seed or {}).get("display") or host,
                        "host": host,
                        "kind": (seed or {}).get("kind") or "domain",
                        "value": (seed or {}).get("value") or host,
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
    kind: str | None = None,
) -> dict:
    from orchestrator.osint.seeds import classify_osint_seed

    seed = classify_osint_seed(target, kind=kind)
    identity = (seed["kind"], seed["value"])
    doc = load_targets_document()
    items: list = list(doc.get("targets") or [])
    for index, item in enumerate(items):
        existing = _entry_seed(item) if isinstance(item, (dict, str)) else None
        if existing and (existing["kind"], existing["value"]) == identity:
            merged = dict(item) if isinstance(item, dict) else {"target": existing.get("display") or existing["value"]}
            merged["target"] = seed["display"]
            merged["value"] = seed["value"]
            merged["kind"] = seed["kind"]
            merged["authorized"] = authorized
            if notes is not None:
                merged["notes"] = notes
            if expiry is not None:
                merged["expiry"] = expiry
            items[index] = merged
            save_targets_document({"targets": items})
            audit_log("AUTHZ_TARGET_UPDATED", {"target": seed["value"], "kind": seed["kind"], "authorized": authorized})
            return merged

    entry = {
        "target": seed["display"],
        "value": seed["value"],
        "kind": seed["kind"],
        "authorized": authorized,
        "added_at": datetime.now().isoformat(timespec="seconds"),
    }
    if notes:
        entry["notes"] = notes
    if expiry:
        entry["expiry"] = expiry
    items.append(entry)
    save_targets_document({"targets": items})
    audit_log("AUTHZ_TARGET_ADDED", {"target": seed["value"], "kind": seed["kind"], "authorized": authorized})
    return entry


def remove_target_entry(target: str, *, kind: str | None = None) -> bool:
    from orchestrator.osint.seeds import classify_osint_seed

    try:
        seed = classify_osint_seed(target, kind=kind)
    except ValueError as exc:
        raise ValueError("invalid target") from exc
    identity = (seed["kind"], seed["value"])
    doc = load_targets_document()
    items: list = list(doc.get("targets") or [])
    kept: list = []
    removed = False
    for item in items:
        existing = _entry_seed(item) if isinstance(item, (dict, str)) else None
        if existing and (existing["kind"], existing["value"]) == identity:
            removed = True
            continue
        kept.append(item)
    if removed:
        save_targets_document({"targets": kept})
        audit_log("AUTHZ_TARGET_REMOVED", {"target": seed["value"], "kind": seed["kind"]})
    return removed


class AuthorizationEnforcer:
    """
    Default: allow scans (authorized engagements) and audit them.
    Set FIREBREAK_REQUIRE_AUTHZ=true and populate authorized_targets.json to enforce.
    """

    @staticmethod
    def _authorized_seeds() -> set[tuple[str, str]]:
        path = targets_file_path()
        if not path.is_file():
            return set()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("targets") or data.get("hosts") or []
        else:
            items = []
        allowed: set[tuple[str, str]] = set()
        for item in items:
            if isinstance(item, dict) and not _entry_active(item):
                continue
            seed = _entry_seed(item)
            if not seed:
                continue
            allowed.add((seed["kind"], seed["value"]))
            if seed["kind"] == "domain":
                host = seed["value"]
                if host.startswith("www."):
                    allowed.add(("domain", host[4:]))
                else:
                    allowed.add(("domain", f"www.{host}"))
        return allowed

    @staticmethod
    def check(target: str, *, kind: str | None = None) -> bool:
        require = os.getenv("FIREBREAK_REQUIRE_AUTHZ", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not require:
            return True
        from orchestrator.osint.seeds import classify_osint_seed

        try:
            seed = classify_osint_seed(target, kind=kind)
        except ValueError:
            host = _normalize_host(target)
            if not host:
                return False
            seed = {"kind": "domain", "value": host}
        allowed = AuthorizationEnforcer._authorized_seeds()
        key = (seed["kind"], seed["value"])
        if key in allowed:
            return True
        if seed["kind"] == "domain":
            host = seed["value"]
            www = host[4:] if host.startswith("www.") else f"www.{host}"
            return ("domain", host) in allowed or ("domain", www) in allowed
        return False

    @staticmethod
    def check_seeds(seeds: list[dict[str, str]]) -> bool:
        if not seeds:
            return True
        return all(AuthorizationEnforcer.check(str(s.get("value") or ""), kind=s.get("kind")) for s in seeds)

    @staticmethod
    def denial_message(target: str) -> str:
        return (
            f"'{target}' is not on the authorized-target list. Add it under "
            "Admin → Targets (or authorized_targets.json) before launching."
        )

    class Denied(PermissionError):
        """Raised when a launch target/seed is outside the authorized allowlist."""

        reason = "unauthorized_target"

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


def enforce_launch_authorization(
    target: str,
    *,
    osint_seeds: list[dict[str, str]] | None = None,
    posture: str | None = None,
    path: str | None = None,
) -> list[dict[str, str]]:
    """Gate every mission launch path through the authorized-target allowlist.

    Returns the normalized OSINT seeds when the launch is authorized.
    Raises ``AuthorizationEnforcer.Denied`` (a ``PermissionError``) otherwise,
    emitting a high-severity audit event. A no-op (allow) when
    ``FIREBREAK_REQUIRE_AUTHZ`` is disabled.
    """
    from orchestrator.osint.seeds import normalize_osint_seeds

    seeds = normalize_osint_seeds(osint_seeds)
    authorized = AuthorizationEnforcer.check(target)
    if seeds:
        authorized = authorized and AuthorizationEnforcer.check_seeds(seeds)
    if not authorized:
        audit_log(
            "MISSION_AUTHZ_DENIED",
            {"target": target, "posture": posture, "osint_seeds": seeds, "path": path},
            severity="high",
        )
        raise AuthorizationEnforcer.Denied(AuthorizationEnforcer.denial_message(target))
    return seeds
