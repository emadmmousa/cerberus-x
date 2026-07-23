"""Map AI Lab scaffolds to executable mission tool bundles.

Each scaffold from ``scaffold_catalog`` can be scheduled in a playbook or AI plan
as ``scaffold/<id>``. At execution time ``build_phase_workflow`` expands the virtual
tool into real Celery wrapper tasks.
"""

from __future__ import annotations

from typing import Any

from orchestrator.ai.scaffold_catalog import cyber_scaffold_catalog
from tools.normalize_args import default_args_for

SCAFFOLD_PREFIX = "scaffold/"
EXPECTED_SCAFFOLD_COUNT = 160

# Default tool bundles per scaffold category (aggressive posture).
CATEGORY_TOOLS: dict[str, list[str]] = {
    "Core platform": ["rustscan", "nmap", "whatweb", "nuclei"],
    "Reconnaissance & OSINT": [
        "theharvester",
        "subfinder",
        "amass",
        "gau",
        "waybackurls",
        "sherlock",
        "darkweb",
        "breach_intel",
    ],
    "Network & infrastructure": ["rustscan", "masscan", "naabu", "nmap", "zmap", "dnsx"],
    "Web application security": [
        "katana",
        "httpx",
        "feroxbuster",
        "ffuf",
        "gobuster",
        "whatweb",
        "arjun",
    ],
    "Vulnerability assessment": ["nuclei", "nikto", "sslscan", "whatweb"],
    "Exploitation & offensive": ["sqlmap", "commix", "xsstrike", "dalfox", "metasploit"],
    "Post-exploitation & lateral movement": [
        "crackmapexec",
        "impacket",
        "responder",
        "bloodhound",
        "linpeas",
        "winpeas",
        "sliver",
    ],
    "Cloud & container security": ["nuclei", "httpx", "katana", "ffuf"],
    "Identity & access": ["hydra", "crackmapexec", "enum4linux", "breach_intel"],
    "Defensive & blue team": ["nuclei", "nikto", "nmap", "sslscan", "whatweb"],
    "Threat intelligence": ["darkweb", "breach_intel", "theharvester", "gau"],
    "Malware & reverse engineering": ["nuclei", "httpx"],
    "Mobile, IoT & embedded": ["nuclei", "nikto", "whatweb"],
    "Wireless & physical": ["nmap", "rustscan"],
    "Compliance & GRC": ["nuclei", "nikto", "sslscan", "whatweb"],
    "ICS / OT": ["nmap", "masscan", "nuclei"],
    "AI / ML security": ["nuclei", "httpx", "katana"],
    "Cryptography & PKI": ["sslscan", "nmap", "whatweb"],
    "Forensics & incident response": ["nuclei", "httpx", "theharvester"],
    "Purple team & orchestration": ["rustscan", "nmap", "nuclei", "ffuf", "sqlmap"],
    "Commercial LLM providers": ["rustscan", "nmap", "nuclei"],
}

# Keyword → tool hints applied before category defaults.
_KEYWORD_TOOLS: tuple[tuple[tuple[str, ...], list[str]], ...] = (
    (("sql", "sqli", "injection"), ["sqlmap", "nuclei"]),
    (("xss",), ["dalfox", "xsstrike", "nuclei"]),
    (("command", "rce", "shell"), ["commix", "sqlmap", "metasploit"]),
    (("subdomain", "dns", "passive"), ["subfinder", "amass", "dnsx", "theharvester"]),
    (("osint", "breach", "harvest", "intel"), ["theharvester", "subfinder", "gau", "darkweb", "breach_intel"]),
    (("dark", "onion", "tor"), ["darkweb", "breach_intel"]),
    (("port", "scan", "network"), ["rustscan", "masscan", "naabu", "nmap"]),
    (("web", "crawl", "api", "graphql", "jwt", "oauth", "cors", "ssrf", "csrf", "ssti", "upload", "websocket", "cms"), ["katana", "httpx", "feroxbuster", "ffuf", "arjun"]),
    (("nuclei", "cve", "vuln", "misconfig"), ["nuclei", "nikto"]),
    (("ssl", "tls", "cipher", "pki", "crypto"), ["sslscan", "nmap"]),
    (("metasploit", "exploit", "payload", "msf"), ["metasploit", "nmap"]),
    (("hydra", "spray", "password", "mfa", "oauth", "oidc", "ldap"), ["hydra", "crackmapexec"]),
    (("kerberoast", "bloodhound", "ad ", "active directory", "smb", "pass-the", "lateral", "domain"), ["bloodhound", "crackmapexec", "impacket", "responder", "enum4linux"]),
    (("privesc", "privilege", "peas", "postex", "persistence", "c2", "implant", "exfil", "ransomware"), ["linpeas", "winpeas", "sliver", "impacket"]),
    (("cloud", "aws", "azure", "gcp", "kubernetes", "k8s", "docker", "terraform", "serverless", "iam", "storage"), ["nuclei", "httpx", "katana", "ffuf"]),
    (("waf", "evasion", "bypass", "proxy", "firewall"), ["ffuf", "sqlmap", "nuclei"]),
    (("wordpress", "cms"), ["wpscan", "nuclei", "nikto"]),
    (("report", "executive", "risk", "purple", "orchestrat", "decision", "plan"), ["nuclei", "nmap", "whatweb"]),
)

# Explicit scaffold id overrides (highest priority).
SCAFFOLD_OVERRIDES: dict[str, list[str]] = {
    "osint-collector": ["theharvester", "subfinder", "gau", "sherlock", "darkweb", "breach_intel"],
    "subdomain-enum": ["subfinder", "amass", "dnsx", "theharvester"],
    "dns-recon": ["dnsx", "subfinder", "theharvester"],
    "passive-recon": ["subfinder", "amass", "gau", "waybackurls", "theharvester"],
    "active-recon": ["rustscan", "naabu", "nmap", "whatweb"],
    "breach-intel": ["breach_intel", "darkweb", "theharvester"],
    "darkweb-monitor": ["darkweb", "breach_intel"],
    "port-scan": ["rustscan", "masscan", "naabu", "nmap"],
    "network-mapper": ["nmap", "rustscan", "dnsx"],
    "service-fingerprint": ["nmap", "whatweb", "httpx"],
    "web-crawler": ["katana", "httpx", "gau", "waybackurls"],
    "api-security": ["httpx", "arjun", "katana", "nuclei"],
    "xss-hunter": ["dalfox", "xsstrike", "nuclei"],
    "sql-injection": ["sqlmap", "nuclei", "katana"],
    "command-injection": ["commix", "sqlmap"],
    "nuclei-runner": ["nuclei"],
    "cve-matcher": ["nuclei", "nmap", "whatweb"],
    "ssl-tls-audit": ["sslscan", "nmap"],
    "metasploit-operator": ["metasploit", "nmap"],
    "password-spray": ["hydra", "crackmapexec"],
    "kerberoast": ["bloodhound", "crackmapexec", "impacket"],
    "bloodhound-analyst": ["bloodhound", "crackmapexec"],
    "lateral-movement": ["crackmapexec", "impacket", "responder"],
    "credential-dump": ["impacket", "crackmapexec"],
    "pass-the-hash": ["crackmapexec", "impacket", "responder"],
    "privilege-escalation": ["linpeas", "winpeas"],
    "c2-operator": ["sliver"],
    "tool-orchestrator": ["rustscan", "nmap", "katana", "nuclei", "ffuf", "sqlmap"],
    "decision-engine": ["nuclei", "nmap", "whatweb"],
    "plan-phase": ["rustscan", "nmap", "whatweb"],
    "hardening-advisor": ["nuclei", "nikto", "sslscan"],
    "waf-tuning": ["ffuf", "nuclei", "sqlmap"],
    "cms-scanner": ["wpscan", "nuclei", "nikto"],
    "google-dorking": ["gau", "waybackurls", "theharvester"],
    "metadata-harvest": ["theharvester", "gau"],
    "advanced-web-recon": [
        "subfinder",
        "amass",
        "httpx",
        "katana",
        "gau",
        "waybackurls",
        "arjun",
        "feroxbuster",
        "nuclei",
        "wpscan",
    ],
    "sqli-recon-chain": ["subfinder", "gau", "katana", "sqlmap", "nuclei"],
    "xss-hunt-chain": ["gau", "katana", "dalfox", "xsstrike", "nuclei"],
    "waf-bypass-strike": ["ffuf", "sqlmap", "nuclei", "dalfox", "whatweb"],
    "api-endpoint-strike": ["katana", "arjun", "ffuf", "httpx", "nuclei"],
    "cred-spray-strike": ["hydra", "crackmapexec", "enum4linux", "nuclei"],
    "ssrf-strike-chain": ["katana", "httpx", "ffuf", "nuclei"],
    "sqli-impact-strike": ["sqlmap", "nuclei", "katana", "ffuf"],
    "xss-chain-strike": ["dalfox", "xsstrike", "nuclei"],
    "ad-domain-strike": ["bloodhound", "crackmapexec", "impacket", "enum4linux"],
    "cloud-misconfig-strike": ["nuclei", "httpx", "katana", "ffuf"],
    "full-surface-strike": ["subfinder", "amass", "rustscan", "httpx", "whatweb"],
}

_FALLBACK_TOOLS = ["rustscan", "nmap", "whatweb", "nuclei"]

# Populated at import — one resolved bundle per catalog id (all 151 specialists).
SCAFFOLD_REGISTRY: dict[str, list[str]] = {}


def _resolve_bundle_raw(scaffold_id: str) -> list[str]:
    """Resolve a scaffold id without using SCAFFOLD_REGISTRY (build-time only)."""
    sid = (scaffold_id or "").strip().lower()
    if not sid:
        return list(_FALLBACK_TOOLS)

    if sid in SCAFFOLD_OVERRIDES:
        return list(SCAFFOLD_OVERRIDES[sid])

    row = _catalog_by_id().get(sid) or {}
    label = str(row.get("label") or sid)
    category = str(row.get("category") or "")

    keyword_tools = _tools_from_keywords(sid, label, category)
    if keyword_tools:
        return keyword_tools

    category_tools = CATEGORY_TOOLS.get(category)
    if category_tools:
        return list(category_tools)

    return list(_FALLBACK_TOOLS)


def _build_registry() -> dict[str, list[str]]:
    catalog = cyber_scaffold_catalog()
    registry: dict[str, list[str]] = {}
    for row in catalog:
        sid = str(row.get("id") or "").strip().lower()
        if not sid:
            continue
        registry[sid] = _resolve_bundle_raw(sid)
    return registry


def refresh_scaffold_registry() -> dict[str, list[str]]:
    """Rebuild and return the full specialist registry."""
    global SCAFFOLD_REGISTRY
    SCAFFOLD_REGISTRY = _build_registry()
    return SCAFFOLD_REGISTRY


def get_scaffold_registry() -> dict[str, list[str]]:
    if not SCAFFOLD_REGISTRY:
        refresh_scaffold_registry()
    return SCAFFOLD_REGISTRY


def assert_all_scaffolds_wired(*, expected: int = EXPECTED_SCAFFOLD_COUNT) -> int:
    """Validate catalog + registry counts and non-empty bundles. Returns count."""
    catalog = cyber_scaffold_catalog()
    registry = get_scaffold_registry()
    if len(catalog) != expected:
        raise AssertionError(f"expected {expected} scaffolds in catalog, got {len(catalog)}")
    if len(registry) != expected:
        raise AssertionError(f"expected {expected} wired scaffolds, got {len(registry)}")
    empty = [sid for sid, tools in registry.items() if not tools]
    if empty:
        raise AssertionError(f"scaffolds with empty bundles: {empty[:5]}")
    ids = {str(row.get("id") or "") for row in catalog}
    if ids != set(registry.keys()):
        missing = ids - set(registry.keys())
        extra = set(registry.keys()) - ids
        raise AssertionError(f"registry mismatch missing={missing} extra={extra}")
    return len(registry)


def is_scaffold_tool(name: str) -> bool:
    return (name or "").strip().startswith(SCAFFOLD_PREFIX)


def scaffold_tool_name(scaffold_id: str) -> str:
    return f"{SCAFFOLD_PREFIX}{(scaffold_id or '').strip().lower()}"


def resolve_scaffold_id(tool_name: str) -> str | None:
    name = (tool_name or "").strip().lower()
    if not name.startswith(SCAFFOLD_PREFIX):
        return None
    sid = name[len(SCAFFOLD_PREFIX) :].strip()
    return sid or None


def _catalog_by_id() -> dict[str, dict[str, Any]]:
    return {str(row.get("id") or ""): row for row in cyber_scaffold_catalog()}


def _tools_from_keywords(scaffold_id: str, label: str, category: str) -> list[str]:
    blob = f"{scaffold_id} {label} {category}".lower()
    matched: list[str] = []
    seen: set[str] = set()
    for keywords, tools in _KEYWORD_TOOLS:
        if any(kw in blob for kw in keywords):
            for tool in tools:
                if tool not in seen:
                    seen.add(tool)
                    matched.append(tool)
    return matched


def tools_for_scaffold(scaffold_id: str) -> list[str]:
    """Resolve scaffold id to an ordered list of real tool names."""
    sid = (scaffold_id or "").strip().lower()
    registry = get_scaffold_registry()
    if sid in registry:
        return list(registry[sid])
    return _resolve_bundle_raw(sid)


def expand_tool_entry(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a single phase tool entry.

    Scaffold entries remain as virtual wrappers (``scaffold/<id>``) so missions
    track specialist recipes as first-class tools. Use ``expand_scaffold_children=True``
    only when callers need flattened CLI tool lists.
    """
    if not isinstance(entry, dict):
        return []
    name = str(entry.get("tool") or "").strip()
    if not is_scaffold_tool(name):
        return [entry]
    return [entry]


def expand_phase_tools(
    tools_list: list[dict[str, Any]],
    *,
    expand_scaffolds: bool = False,
) -> list[dict[str, Any]]:
    """Normalize a phase tool list.

    By default scaffold/* entries stay intact for ``run_scaffold_bundle_task``.
    Pass ``expand_scaffolds=True`` to flatten into underlying CLI wrappers.
    """
    expanded: list[dict[str, Any]] = []
    for entry in tools_list or []:
        if expand_scaffolds and isinstance(entry, dict) and is_scaffold_tool(
            str(entry.get("tool") or "")
        ):
            sid = resolve_scaffold_id(str(entry.get("tool") or "")) or "tool-orchestrator"
            extra_args = entry.get("args") or []
            parallel_hint = bool(entry.get("parallel"))
            for tool in tools_for_scaffold(sid):
                row: dict[str, Any] = {
                    "tool": tool,
                    "args": list(extra_args) if extra_args else default_args_for(tool),
                }
                if parallel_hint:
                    row["parallel"] = True
                expanded.append(row)
        else:
            expanded.extend(expand_tool_entry(entry))
    return expanded


def scaffold_tool_names() -> set[str]:
    return {scaffold_tool_name(row["id"]) for row in cyber_scaffold_catalog() if row.get("id")}


def list_scaffold_tools(*, limit: int | None = None) -> list[dict[str, Any]]:
    """Catalog rows for API: virtual scaffold tool → underlying CLI tools."""
    rows: list[dict[str, Any]] = []
    for entry in cyber_scaffold_catalog():
        sid = str(entry.get("id") or "")
        if not sid:
            continue
        bundle = tools_for_scaffold(sid)
        rows.append(
            {
                "name": scaffold_tool_name(sid),
                "scaffold_id": sid,
                "label": entry.get("label") or sid,
                "category": entry.get("category"),
                "tools": bundle,
                "tool_count": len(bundle),
                "risk": "medium",
                "maturity": "scaffold",
                "description": entry.get("notes") or f"Scaffold bundle: {entry.get('label') or sid}",
            }
        )
        if limit and len(rows) >= limit:
            break
    return rows


def scaffold_summary_for_llm(*, max_rows: int = 20) -> str:
    """Compact roster of scaffold virtual tools for planner prompts."""
    lines = [
        "Scaffold bundles (schedule as scaffold/<id> — expands to real tools at execution):"
    ]
    for row in list_scaffold_tools(limit=max_rows):
        tools = ",".join(row.get("tools") or [])
        lines.append(f"- {row['name']} ({row.get('label')}) → {tools}")
    lines.append(
        f"Full catalog: {len(scaffold_tool_names())} scaffolds (expected {EXPECTED_SCAFFOLD_COUNT}). "
        "Example: scaffold/sql-injection runs sqlmap+nuclei+katana."
    )
    return "\n".join(lines)


# Build registry at import so all 151 specialists are wired before first mission.
refresh_scaffold_registry()
assert_all_scaffolds_wired()
