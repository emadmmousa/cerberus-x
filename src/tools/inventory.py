"""Firebreak tool arsenal inventory — wrappers, binaries, maturity."""

from __future__ import annotations

import os
import shutil
from typing import Any

# Maturity:
#   executable — runs against a target from the worker
#   artifact   — prepares a binary/script for later host-side use
#   helper     — needs credentials / interface / operator action to be useful
#   framework  — Metasploit RPC (thousands of modules behind one tool name)

TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "name": "nmap",
        "category": "port_host",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["nmap"],
        "description": "Service/version port scan",
    },
    {
        "name": "masscan",
        "category": "port_host",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["masscan"],
        "description": "Fast SYN port discovery",
    },
    {
        "name": "rustscan",
        "category": "port_host",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["rustscan"],
        "description": "Fast port discovery",
    },
    {
        "name": "zmap",
        "category": "port_host",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["zmap"],
        "description": "Internet-scale port sweep helper",
    },
    {
        "name": "whatweb",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["whatweb"],
        "description": "Web technology fingerprint",
    },
    {
        "name": "gobuster",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["gobuster"],
        "description": "Directory/path discovery",
    },
    {
        "name": "ffuf",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["ffuf"],
        "description": "Web content fuzzing",
    },
    {
        "name": "theharvester",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["theHarvester", "theharvester"],
        "description": "OSINT emails/hosts",
    },
    {
        "name": "nikto",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["nikto"],
        "description": "Web server misconfiguration scan",
    },
    {
        "name": "nuclei",
        "category": "vuln",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["nuclei"],
        "description": "Template vulnerability scan",
    },
    {
        "name": "xsstrike",
        "category": "vuln",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["xsstrike"],
        "description": "XSS probe",
    },
    {
        "name": "sqlmap",
        "category": "vuln",
        "risk": "high",
        "maturity": "executable",
        "binaries": ["sqlmap"],
        "description": "SQL injection testing",
    },
    {
        "name": "hydra",
        "category": "creds",
        "risk": "high",
        "maturity": "executable",
        "binaries": ["hydra"],
        "description": "Online login guessing",
    },
    {
        "name": "john",
        "category": "creds",
        "risk": "high",
        "maturity": "helper",
        "binaries": ["john"],
        "description": "Offline hash cracking (needs a local hash file)",
    },
    {
        "name": "hashcat",
        "category": "creds",
        "risk": "high",
        "maturity": "helper",
        "binaries": ["hashcat"],
        "description": "GPU/CPU hash cracking (needs a local hash file)",
    },
    {
        "name": "impacket",
        "category": "windows_ad",
        "risk": "high",
        "maturity": "helper",
        "binaries": ["secretsdump.py", "secretsdump"],
        "description": "Windows protocol attacks (secretsdump)",
    },
    {
        "name": "crackmapexec",
        "category": "windows_ad",
        "risk": "high",
        "maturity": "executable",
        "binaries": ["nxc", "crackmapexec", "cme"],
        "description": "Network auth spray / enum (NetExec)",
    },
    {
        "name": "responder",
        "category": "windows_ad",
        "risk": "high",
        "maturity": "helper",
        "binaries": ["responder", "Responder.py"],
        "description": "LLMNR/NBT-NS poisoning helper (needs interface)",
    },
    {
        "name": "bloodhound",
        "category": "windows_ad",
        "risk": "high",
        "maturity": "helper",
        "binaries": ["bloodhound-python", "bloodhound"],
        "description": "AD path collection (needs domain credentials)",
    },
    {
        "name": "winpeas",
        "category": "postex",
        "risk": "high",
        "maturity": "artifact",
        "binaries": [],
        "artifact_paths": ["/app/tools/winPEASx64.exe"],
        "description": "Windows privilege escalation enum artifact",
    },
    {
        "name": "linpeas",
        "category": "postex",
        "risk": "high",
        "maturity": "artifact",
        "binaries": [],
        "artifact_paths": ["/app/tools/linpeas.sh"],
        "description": "Linux privilege escalation enum artifact",
    },
    {
        "name": "sliver",
        "category": "postex",
        "risk": "high",
        "maturity": "helper",
        "binaries": ["sliver-server", "sliver-client", "sliver"],
        "description": "C2 payload helper (optional binary; not auto-installed)",
    },
    {
        "name": "metasploit",
        "category": "exploit",
        "risk": "high",
        "maturity": "framework",
        "binaries": [],
        "description": "Exploit / post-exploitation via msgrpc (module library)",
    },
]


def catalog_by_name() -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in TOOL_CATALOG}


def _any_which(names: list[str]) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _artifact_ready(paths: list[str]) -> str | None:
    for path in paths:
        if path and os.path.isfile(path):
            return path
    return None


def probe_local_tool(entry: dict[str, Any]) -> dict[str, Any]:
    """Probe this host (typically a Celery worker) for one tool."""
    name = entry["name"]
    maturity = entry.get("maturity", "executable")
    binaries = list(entry.get("binaries") or [])
    artifacts = list(entry.get("artifact_paths") or [])

    found_bin = _any_which(binaries) if binaries else None
    found_art = _artifact_ready(artifacts) if artifacts else None

    if name == "metasploit":
        # RPC lives in a separate container; wrapper talks over the network.
        status = "framework"
        detail = "Uses Metasploit RPC (separate service), not a local binary"
        ready = True
    elif maturity == "artifact":
        ready = bool(found_art)
        status = "ready" if ready else "missing_artifact"
        detail = found_art or "artifact not present under /app/tools"
    elif found_bin:
        ready = True
        status = "ready"
        detail = found_bin
    elif maturity in {"helper", "artifact"} and not binaries:
        ready = False
        status = "unavailable"
        detail = "no binary probe configured"
    else:
        ready = False
        status = "missing_binary"
        detail = f"none of {binaries} found on PATH" if binaries else "not available"

    return {
        "name": name,
        "category": entry.get("category"),
        "risk": entry.get("risk", "low"),
        "maturity": maturity,
        "description": entry.get("description", ""),
        "ready": ready,
        "status": status,
        "detail": detail,
        "wired": True,
    }


def probe_all_local() -> dict[str, Any]:
    tools = [probe_local_tool(entry) for entry in TOOL_CATALOG]
    ready = sum(1 for t in tools if t["ready"])
    return {
        "count": len(tools),
        "ready": ready,
        "missing": len(tools) - ready,
        "tools": tools,
    }


def list_catalog(*, category: str | None = None, risk: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for entry in TOOL_CATALOG:
        if category and entry.get("category") != category:
            continue
        if risk and entry.get("risk") != risk:
            continue
        rows.append(
            {
                "name": entry["name"],
                "category": entry["category"],
                "risk": entry["risk"],
                "maturity": entry["maturity"],
                "description": entry["description"],
                "binaries": list(entry.get("binaries") or []),
            }
        )
    return rows
