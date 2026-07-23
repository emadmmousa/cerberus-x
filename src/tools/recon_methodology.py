"""Advanced web recon methodology — maps operator playbooks to Firebreak tools."""

from __future__ import annotations

from typing import Any

# Each step: id, title, tools, notes (CLI patterns use TARGET-DOMAIN.COM placeholder).
RECON_PHASES: tuple[dict[str, Any], ...] = (
    {
        "id": "subdomain_enum",
        "title": "Recursive subdomain enumeration",
        "tools": ["subfinder", "amass"],
        "cli": ["subfinder -d TARGET-DOMAIN.COM -all -recursive"],
    },
    {
        "id": "live_hosts",
        "title": "Alive host filtering",
        "tools": ["httpx"],
        "cli": ["httpx -ports 80,443,8080,8000,8888 -threads 200"],
    },
    {
        "id": "passive_urls",
        "title": "Passive URL harvest",
        "tools": ["katana", "gau", "waybackurls"],
        "cli": [
            "katana -u https://TARGET-DOMAIN.COM -d 5 -ps -pss waybackarchive,commoncrawl,alienvault",
            "gau --mc 200 TARGET-DOMAIN.COM",
        ],
    },
    {
        "id": "param_discovery",
        "title": "Hidden parameter discovery",
        "tools": ["arjun", "katana"],
        "cli": ["arjun -u https://TARGET-DOMAIN.COM/ -m GET,POST --passive"],
    },
    {
        "id": "tech_fingerprint",
        "title": "Technology fingerprint",
        "tools": ["whatweb", "httpx", "wappalyzer"],
        "cli": ["httpx -tech-detect -sc -title -server"],
    },
    {
        "id": "dir_bruteforce",
        "title": "Directory bruteforce",
        "tools": ["feroxbuster", "ffuf", "gobuster"],
        "cli": ["ffuf -u https://TARGET-DOMAIN.COM/FUZZ -recursion -recursion-depth 2"],
    },
    {
        "id": "vuln_scan",
        "title": "Template and exposure scan",
        "tools": ["nuclei", "nikto"],
        "cli": ["nuclei -severity critical,high,medium"],
    },
    {
        "id": "sqli_candidates",
        "title": "SQLi candidate filtering",
        "tools": ["gau", "katana", "sqlmap"],
        "cli": ["gau TARGET-DOMAIN.COM | grep '='"],
    },
    {
        "id": "xss_hunt",
        "title": "XSS pipeline",
        "tools": ["gau", "dalfox", "xsstrike", "nuclei"],
        "cli": ["dalfox pipe --waf-bypass --silence"],
    },
    {
        "id": "cors_check",
        "title": "CORS misconfiguration",
        "tools": ["httpx", "nuclei"],
        "cli": ['curl -H "Origin: https://evil.com" -I https://TARGET-DOMAIN.COM/api/'],
    },
    {
        "id": "wordpress",
        "title": "WordPress aggressive scan",
        "tools": ["wpscan", "nuclei"],
        "cli": ["wpscan --url https://TARGET-DOMAIN.COM --enumerate ap --plugins-detection aggressive"],
    },
    {
        "id": "port_scan",
        "title": "Port and service discovery",
        "tools": ["naabu", "nmap", "masscan", "rustscan"],
        "cli": ["naabu -top-ports 1000", "nmap -p- --min-rate 1000 -T4 -A TARGET-DOMAIN.COM"],
    },
    {
        "id": "google_dorks",
        "title": "Search engine dorking",
        "tools": ["gau", "theharvester"],
        "module": "google_dorks",
    },
    {
        "id": "ssti_probe",
        "title": "SSTI quick probe",
        "tools": ["httpx", "ffuf"],
        "cli": ['qsreplace "{{7*7}}" | httpx -mc 200 -fr'],
    },
    {
        "id": "ssrf_candidates",
        "title": "SSRF parameter filter",
        "tools": ["katana", "gau", "httpx"],
        "cli": ["grep -Ei '(url=|dest=|redirect=|next=|callback=)'"],
    },
)

FULL_WEB_RECON_TOOLS: tuple[str, ...] = (
    "subfinder",
    "amass",
    "dnsx",
    "httpx",
    "katana",
    "gau",
    "waybackurls",
    "arjun",
    "whatweb",
    "feroxbuster",
    "ffuf",
    "nuclei",
    "nikto",
    "wpscan",
    "dalfox",
    "xsstrike",
    "sqlmap",
    "naabu",
    "nmap",
    "theharvester",
    "sherlock",
    "breach_intel",
    "darkweb",
)


def phase_by_id(phase_id: str) -> dict[str, Any] | None:
    pid = (phase_id or "").strip().lower()
    for row in RECON_PHASES:
        if row.get("id") == pid:
            return dict(row)
    return None


def tools_for_phase(phase_id: str) -> list[str]:
    row = phase_by_id(phase_id)
    if not row:
        return []
    return list(row.get("tools") or [])


def methodology_summary(*, max_phases: int = 8) -> str:
    lines = ["Advanced web recon methodology (authorized targets only):"]
    for row in RECON_PHASES[:max_phases]:
        tools = ", ".join(row.get("tools") or [])
        lines.append(f"- {row.get('title')}: {tools}")
    lines.append(f"Full rotation ({len(FULL_WEB_RECON_TOOLS)} tools): " + ", ".join(FULL_WEB_RECON_TOOLS[:12]) + ", …")
    return "\n".join(lines)
