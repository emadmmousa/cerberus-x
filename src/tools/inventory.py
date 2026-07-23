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
        "description": "Public OSINT — harvest emails and subdomains from open sources",
    },
    {
        "name": "subfinder",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["subfinder"],
        "description": "Passive subdomain scrape — ProjectDiscovery subfinder",
    },
    {
        "name": "gau",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["gau"],
        "description": "Archive URL scrape — wayback/OTX/urlscan passive URLs",
    },
    {
        "name": "sherlock",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["sherlock"],
        "description": "Username OSINT — scrape public profiles across hundreds of sites",
    },
    {
        "name": "darkweb",
        "category": "dark_web",
        "risk": "medium",
        "maturity": "executable",
        "binaries": ["curl"],
        "description": "Hidden-web OSINT — scrape indexes and Tor services for seed matches",
    },
    {
        "name": "breach_intel",
        "category": "dark_web",
        "risk": "medium",
        "maturity": "executable",
        "binaries": [],
        "description": "Breach DB lookup — match DeHashed + LeakCheck records to OSINT seeds",
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
        "name": "httpx",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["pd-httpx", "httpx"],
        "description": "HTTP probe and tech fingerprint",
    },
    {
        "name": "katana",
        "category": "web_recon",
        "risk": "medium",
        "maturity": "executable",
        "binaries": ["katana"],
        "description": "Web crawler for endpoint discovery",
    },
    {
        "name": "feroxbuster",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["feroxbuster"],
        "description": "Fast recursive web content discovery",
    },
    {
        "name": "naabu",
        "category": "port_host",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["naabu"],
        "description": "Fast port scanner (ProjectDiscovery)",
    },
    {
        "name": "dnsx",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["dnsx"],
        "description": "DNS enumeration and resolution toolkit",
    },
    {
        "name": "amass",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["amass"],
        "description": "Passive subdomain enumeration (OWASP Amass)",
    },
    {
        "name": "dalfox",
        "category": "vuln",
        "risk": "medium",
        "maturity": "executable",
        "binaries": ["dalfox"],
        "description": "Parameter-aware XSS scanner",
    },
    {
        "name": "waybackurls",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["waybackurls"],
        "description": "Historical URL discovery from Wayback",
    },
    {
        "name": "sslscan",
        "category": "vuln",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["sslscan"],
        "description": "SSL/TLS cipher and certificate audit",
    },
    {
        "name": "arjun",
        "category": "web_recon",
        "risk": "low",
        "maturity": "executable",
        "binaries": ["arjun"],
        "description": "HTTP parameter discovery",
    },
    {
        "name": "enum4linux",
        "category": "windows_ad",
        "risk": "high",
        "maturity": "executable",
        "binaries": ["enum4linux-ng"],
        "description": "SMB/NetBIOS/LDAP enumeration",
    },
    {
        "name": "commix",
        "category": "vuln",
        "risk": "high",
        "maturity": "executable",
        "binaries": ["python3"],
        "description": "Automated command injection detection",
    },
    {
        "name": "wpscan",
        "category": "vuln",
        "risk": "medium",
        "maturity": "executable",
        "binaries": ["wpscan"],
        "description": "WordPress vulnerability scanner",
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


def _slug_scaffold_category(category: str) -> str:
    return (
        (category or "scaffold")
        .lower()
        .replace(" & ", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )[:48]


def scaffold_inventory_rows() -> list[dict[str, Any]]:
    from orchestrator.ai.scaffold_tools import EXPECTED_SCAFFOLD_COUNT, list_scaffold_tools

    rows: list[dict[str, Any]] = []
    for item in list_scaffold_tools():
        rows.append(
            {
                "name": item["name"],
                "category": _slug_scaffold_category(str(item.get("category") or "scaffold")),
                "risk": item.get("risk") or "medium",
                "maturity": "scaffold",
                "binaries": [],
                "bundle_tools": list(item.get("tools") or []),
                "scaffold_id": item.get("scaffold_id"),
                "description": item.get("description")
                or f"Specialist scaffold: {item.get('label') or item.get('scaffold_id')}",
            }
        )
    if len(rows) != EXPECTED_SCAFFOLD_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_SCAFFOLD_COUNT} scaffold inventory rows, got {len(rows)}"
        )
    return rows


CLI_TOOL_CATALOG: list[dict[str, Any]] = TOOL_CATALOG
TOOL_CATALOG = CLI_TOOL_CATALOG + scaffold_inventory_rows()


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
    elif maturity == "scaffold":
        bundle = entry.get("bundle_tools") or []
        ready = bool(bundle)
        status = "scaffold"
        preview = ", ".join(bundle[:4])
        if len(bundle) > 4:
            preview += ", …"
        detail = f"Specialist bundle ({len(bundle)} tools): {preview}"
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
