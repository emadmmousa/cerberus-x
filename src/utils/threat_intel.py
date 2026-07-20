"""Lightweight threat-intel hints for AI decisioning (offline-safe)."""

from __future__ import annotations

from typing import Dict, List


# Minimal local map — no outbound CVE API calls by default.
_SERVICE_HINTS = {
    "http": ["check web vulns", "nuclei", "nikto"],
    "https": ["check tls + web vulns", "nuclei"],
    "ssh": ["hydra brute cautious", "check weak keys"],
    "ftp": ["anonymous login", "hydra"],
    "smtp": ["user enum"],
    "microsoft-ds": ["smb checks", "crackmapexec"],
    "ms-wbt-server": ["rdp exposure"],
    "mysql": ["sqlmap if web front present"],
    "postgresql": ["auth hardening"],
}


class ThreatIntelFetcher:
    def fetch_for_services(self, services: List[str]) -> Dict[str, List[str]]:
        hits: Dict[str, List[str]] = {}
        for svc in services or []:
            key = str(svc).strip().lower()
            if key in _SERVICE_HINTS:
                hits[key] = list(_SERVICE_HINTS[key])
        return hits
