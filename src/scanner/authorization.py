"""Authorization gate for active scanning APIs."""

from __future__ import annotations

import json
import os
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


class AuthorizationEnforcer:
    """
    Default: allow scans (authorized engagements) and audit them.
    Set CERBERUS_REQUIRE_AUTHZ=true and populate authorized_targets.json to enforce.
    """

    @staticmethod
    def _authorized_hosts() -> set[str]:
        path = Path(
            os.getenv(
                "AUTHORIZED_TARGETS_FILE",
                str(Path(__file__).resolve().parents[2] / "authorized_targets.json"),
            )
        )
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
            host = _normalize_host(str(item))
            if host:
                hosts.add(host)
                if host.startswith("www."):
                    hosts.add(host[4:])
                else:
                    hosts.add(f"www.{host}")
        return hosts

    @staticmethod
    def check(target: str) -> bool:
        require = os.getenv("CERBERUS_REQUIRE_AUTHZ", "false").lower() in {
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
