"""
Authorized offensive attack method catalog for Firebreak.

Aggregates kill-chain methods, tool rotations, WAF/SQLi technique families,
and aggressive argv defaults. Used by planner, runner, and chat compile paths.
"""

from __future__ import annotations

from typing import Any, Literal

from orchestrator.ai.posture import Posture, normalize_posture

KillPhase = Literal[
    "recon",
    "dark_web",
    "discovery",
    "vuln",
    "creds",
    "windows_ad",
    "postex",
    "exploit",
    "evasion",
]

# Full kill-chain tool order — every wired Firebreak wrapper, aggressive posture.
FULL_TOOL_ROTATION: tuple[str, ...] = (
    "rustscan",
    "masscan",
    "naabu",
    "nmap",
    "zmap",
    "dnsx",
    "amass",
    "subfinder",
    "whatweb",
    "theharvester",
    "gau",
    "waybackurls",
    "sherlock",
    "darkweb",
    "breach_intel",
    "httpx",
    "katana",
    "feroxbuster",
    "gobuster",
    "ffuf",
    "arjun",
    "sslscan",
    "nuclei",
    "nikto",
    "wpscan",
    "xsstrike",
    "dalfox",
    "commix",
    "sqlmap",
    "hydra",
    "enum4linux",
    "john",
    "hashcat",
    "crackmapexec",
    "impacket",
    "responder",
    "bloodhound",
    "metasploit",
    "winpeas",
    "linpeas",
    "sliver",
)

AGGRESSIVE_ARGS: dict[str, list[str]] = {
    "rustscan": ["--ulimit", "5000", "--top"],
    "masscan": ["-p80,443,22,8080,8443,3389,445", "--rate=1000", "--wait=0"],
    "nmap": ["-sV", "-p21,22,80,443,8080,8443,3389,445", "-T4"],
    "zmap": ["-p", "80,443,22,445,3389"],
    "whatweb": ["-a", "3"],
    "theharvester": ["-b", "crtsh"],
    "subfinder": ["-silent"],
    "gau": ["--subs"],
    "sherlock": ["--print-found", "--no-color"],
    "katana": ["-d", "3", "-jc", "-silent"],
    "httpx": ["-silent", "-status-code", "-title", "-tech-detect"],
    "darkweb": ["--method", "full"],
    "breach_intel": ["--limit", "25"],
    "gobuster": ["dir", "-w", "/usr/share/dirb/wordlists/common.txt"],
    "ffuf": ["-ac"],
    "nuclei": [
        "-t",
        "http/cves/",
        "-severity",
        "critical,high,medium",
        "-tags",
        "cve,kev,rce,sqli,xss",
        "-silent",
    ],
    "nikto": ["-maxtime", "120"],
    "xsstrike": ["--timeout", "30", "--skip"],
    "sqlmap": [
        "--batch",
        "--forms",
        "--crawl=3",
        "--level=5",
        "--risk=3",
        "--technique=BEUSTQ",
        "--threads=4",
    ],
    "hydra": [],
    "metasploit": ["auxiliary/scanner/portscan/tcp"],
    "crackmapexec": [],
    "impacket": [],
    "responder": [],
    "bloodhound": [],
    "john": [],
    "hashcat": [],
    "winpeas": [],
    "linpeas": [],
    "sliver": [],
    "feroxbuster": ["-q"],
    "naabu": ["-top-ports", "1000", "-silent"],
    "dnsx": ["-silent", "-a", "-aaaa", "-cname", "-mx"],
    "amass": ["enum", "-passive"],
    "dalfox": ["--silence", "--skip-bav"],
    "waybackurls": [],
    "sslscan": ["--no-failed"],
    "arjun": ["--stable"],
    "enum4linux": ["-A"],
    "commix": ["--batch", "--level=2"],
    "wpscan": ["--no-update", "--random-user-agent", "--enumerate", "vp,vt"],
}

GOAL_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("sql", "sqli", "injection", "database", "dbms", "mysql", "postgres", "mssql", "oracle"), "sqlmap"),
    (("database dump", "data access", "get into the database", "db access"), "sqlmap"),
    (("xss", "cross-site", "cross site"), "dalfox"),
    (("xss", "cross-site", "cross site"), "xsstrike"),
    (("command inject", "commix", "os command"), "commix"),
    (("wordpress", "wp ", "wp-"), "wpscan"),
    (("tls", "ssl", "cipher"), "sslscan"),
    (("param", "arjun", "hidden param"), "arjun"),
    (("enum4linux", "smb enum", "netbios"), "enum4linux"),
    (("amass", "passive subdomain"), "amass"),
    (("naabu", "fast port"), "naabu"),
    (("feroxbuster", "recursive content"), "feroxbuster"),
    (("wayback", "historical"), "waybackurls"),
    (("brute", "bruteforce", "password", "login", "credential"), "hydra"),
    (("hash", "crack", "john", "hashcat"), "john"),
    (("exploit", "shell", "rce", "metasploit", "msf", "payload", "cve"), "metasploit"),
    (("dir", "content", "fuzz", "endpoint", "path"), "ffuf"),
    (("cve", "vuln", "vulnerab", "nuclei"), "nuclei"),
    (("osint", "email", "harvest", "subdomain"), "theharvester"),
    (("subdomain", "subfinder", "passive dns"), "subfinder"),
    (("archive", "wayback", "historical url", "gau"), "gau"),
    (("username", "social profile", "sherlock", "maigret"), "sherlock"),
    (("crawl", "spider", "surface map", "katana"), "katana"),
    (("probe", "httpx", "live url"), "httpx"),
    (("fingerprint", "whatweb", "tech stack"), "whatweb"),
    (("dark web", "darkweb", "dark-web", "onion", r"\btor\b", "hidden service"), "darkweb"),
    (("leak", "breach", "paste", "dump", "underground"), "darkweb"),
    (("dehashed", "leakcheck", "credential exposure", "data breach"), "breach_intel"),
    (("smb", "active directory", r"\bad\b", "ldap", "ntlm"), "crackmapexec"),
    (("lateral", "secretsdump", "impacket", "relay"), "impacket"),
    (("poison", "llmnr", "responder", "nbt-ns"), "responder"),
    (("bloodhound", "ad path", "kerberoast"), "bloodhound"),
    (("privesc", "privilege", "peas", "linpeas", "winpeas"), "linpeas"),
    (("c2", "sliver", "beacon", "implant"), "sliver"),
    (("port", "scan", "masscan", "rustscan"), "rustscan"),
    (("waf", "bypass", "evasion", "cdn"), "ffuf"),
)

METHOD_CATALOG: list[dict[str, Any]] = [
    {
        "id": "port_sweep",
        "phase": "recon",
        "name": "Fast port discovery",
        "tools": ["rustscan", "masscan", "naabu", "zmap"],
        "risk": "low",
    },
    {
        "id": "service_enum",
        "phase": "recon",
        "name": "Service/version fingerprint",
        "tools": ["nmap", "whatweb"],
        "risk": "low",
    },
    {
        "id": "osint_harvest",
        "phase": "recon",
        "name": "Public OSINT harvest (emails, subdomains)",
        "tools": ["theharvester"],
        "risk": "low",
    },
    {
        "id": "osint_subdomain_scrape",
        "phase": "recon",
        "name": "Passive subdomain scrape",
        "tools": ["subfinder", "amass", "dnsx"],
        "risk": "low",
    },
    {
        "id": "osint_archive_scrape",
        "phase": "recon",
        "name": "Archive and passive URL scrape",
        "tools": ["gau", "waybackurls"],
        "risk": "low",
    },
    {
        "id": "osint_username_scrape",
        "phase": "recon",
        "name": "Username presence scrape across public sites",
        "tools": ["sherlock"],
        "risk": "low",
    },
    {
        "id": "osint_web_crawl",
        "phase": "recon",
        "name": "Aggressive web surface crawl",
        "tools": ["katana"],
        "risk": "medium",
    },
    {
        "id": "osint_http_probe",
        "phase": "recon",
        "name": "Live HTTP probe and tech scrape",
        "tools": ["httpx", "whatweb"],
        "risk": "low",
    },
    {
        "id": "advanced_web_recon",
        "phase": "recon",
        "name": "Advanced web recon pipeline (subdomains → URLs → params → vuln)",
        "tools": ["subfinder", "httpx", "katana", "gau", "arjun", "nuclei"],
        "risk": "medium",
    },
    {
        "id": "google_dork_recon",
        "phase": "recon",
        "name": "Search-engine dork footprint",
        "tools": ["theharvester", "gau"],
        "risk": "low",
        "techniques": ["google_dorks"],
    },
    {
        "id": "darkweb_onion_search",
        "phase": "dark_web",
        "name": "Dark web onion discovery (Ahmia/index search)",
        "tools": ["darkweb"],
        "risk": "medium",
        "techniques": ["onion_search"],
    },
    {
        "id": "darkweb_mention_scan",
        "phase": "dark_web",
        "name": "Underground mention scan for target/brand",
        "tools": ["darkweb"],
        "risk": "medium",
        "techniques": ["mention_scan", "forum_mention", "market_mention"],
    },
    {
        "id": "darkweb_leak_hunt",
        "phase": "dark_web",
        "name": "Hidden-web leak scrape (paste, dump mentions)",
        "tools": ["darkweb"],
        "risk": "medium",
        "techniques": ["leak_hunt", "paste_monitor", "breach_correlate"],
    },
    {
        "id": "breach_intel_lookup",
        "phase": "dark_web",
        "name": "Breach DB lookup — match leaks to OSINT seeds",
        "tools": ["breach_intel"],
        "risk": "medium",
        "techniques": ["dehashed", "leakcheck"],
    },
    {
        "id": "darkweb_onion_probe",
        "phase": "dark_web",
        "name": "Tor hidden service probe and fingerprint",
        "tools": ["darkweb"],
        "risk": "medium",
        "techniques": ["onion_probe", "tor_fingerprint"],
    },
    {
        "id": "dir_bruteforce",
        "phase": "discovery",
        "name": "Directory and path brute force",
        "tools": ["feroxbuster", "gobuster", "ffuf"],
        "risk": "low",
    },
    {
        "id": "param_discovery",
        "phase": "discovery",
        "name": "Hidden HTTP parameter discovery",
        "tools": ["arjun"],
        "risk": "low",
    },
    {
        "id": "template_vuln_scan",
        "phase": "vuln",
        "name": "CVE/template vulnerability scan",
        "tools": ["nuclei"],
        "risk": "low",
    },
    {
        "id": "web_misconfig",
        "phase": "vuln",
        "name": "Web server misconfiguration scan",
        "tools": ["nikto"],
        "risk": "low",
    },
    {
        "id": "xss_probe",
        "phase": "vuln",
        "name": "Reflected/stored XSS probing",
        "tools": ["dalfox", "xsstrike"],
        "risk": "low",
    },
    {
        "id": "cmd_injection",
        "phase": "exploit",
        "name": "OS command injection probing",
        "tools": ["commix"],
        "risk": "high",
    },
    {
        "id": "cms_audit",
        "phase": "vuln",
        "name": "CMS vulnerability audit",
        "tools": ["wpscan", "nuclei"],
        "risk": "medium",
    },
    {
        "id": "tls_audit",
        "phase": "vuln",
        "name": "SSL/TLS configuration audit",
        "tools": ["sslscan"],
        "risk": "low",
    },
    {
        "id": "sqli_full",
        "phase": "exploit",
        "name": "Full SQL injection (BEUSTQ + crawl/forms)",
        "tools": ["sqlmap"],
        "risk": "high",
        "techniques": ["union", "error", "boolean", "time", "stacked", "inline"],
    },
    {
        "id": "sqli_nuclei",
        "phase": "exploit",
        "name": "Template-based SQLi and injection checks",
        "tools": ["nuclei"],
        "risk": "medium",
        "techniques": ["sqli", "injection", "error-based"],
    },
    {
        "id": "db_path_discovery",
        "phase": "discovery",
        "name": "Database admin panel and backup path fuzzing",
        "tools": ["ffuf", "gobuster"],
        "risk": "low",
        "techniques": ["phpmyadmin", "adminer", "backup", "dump"],
    },
    {
        "id": "leak_intel_scrape",
        "phase": "dark_web",
        "name": "Hidden-web leak scrape for seed matches",
        "tools": ["darkweb", "breach_intel"],
        "risk": "medium",
        "techniques": ["leak_hunt", "breach_correlate", "dehashed", "leakcheck"],
    },
    {
        "id": "db_form_crawl",
        "phase": "discovery",
        "name": "Crawl forms and API params for injectable inputs",
        "tools": ["katana", "httpx"],
        "risk": "low",
        "techniques": ["form_discovery", "param_mining"],
    },
    {
        "id": "online_brute",
        "phase": "creds",
        "name": "Online login brute force",
        "tools": ["hydra"],
        "risk": "high",
    },
    {
        "id": "offline_crack",
        "phase": "creds",
        "name": "Offline hash cracking",
        "tools": ["john", "hashcat"],
        "risk": "high",
    },
    {
        "id": "smb_spray",
        "phase": "windows_ad",
        "name": "SMB auth spray and share enum",
        "tools": ["crackmapexec", "enum4linux"],
        "risk": "high",
    },
    {
        "id": "secrets_dump",
        "phase": "windows_ad",
        "name": "Remote secrets extraction (Impacket)",
        "tools": ["impacket"],
        "risk": "high",
    },
    {
        "id": "llmnr_poison",
        "phase": "windows_ad",
        "name": "LLMNR/NBT-NS poisoning",
        "tools": ["responder"],
        "risk": "high",
    },
    {
        "id": "ad_path_collect",
        "phase": "windows_ad",
        "name": "BloodHound AD path collection",
        "tools": ["bloodhound"],
        "risk": "high",
    },
    {
        "id": "msf_exploit",
        "phase": "exploit",
        "name": "Metasploit module exploitation",
        "tools": ["metasploit"],
        "risk": "high",
    },
    {
        "id": "linux_privesc",
        "phase": "postex",
        "name": "Linux privilege escalation enum",
        "tools": ["linpeas"],
        "risk": "high",
    },
    {
        "id": "windows_privesc",
        "phase": "postex",
        "name": "Windows privilege escalation enum",
        "tools": ["winpeas"],
        "risk": "high",
    },
    {
        "id": "c2_implant",
        "phase": "postex",
        "name": "C2 implant staging (Sliver)",
        "tools": ["sliver"],
        "risk": "high",
    },
    {
        "id": "waf_bypass",
        "phase": "evasion",
        "name": "WAF evasion (encoding, headers, pollution)",
        "tools": ["ffuf", "sqlmap", "nuclei"],
        "risk": "medium",
    },
]

HIGH_RISK_METHODS = frozenset(
    m["id"] for m in METHOD_CATALOG if m.get("risk") == "high"
)


def full_tool_rotation() -> list[str]:
    return list(FULL_TOOL_ROTATION)


def aggressive_args_for(tool: str) -> list[str]:
    from tools.normalize_args import default_args_for

    name = (tool or "").strip().lower()
    base = AGGRESSIVE_ARGS.get(name)
    if base is not None:
        return list(base)
    return default_args_for(name)


def next_rotation_tool(
    allow: set[str],
    *,
    tried: set[str],
    failed: set[str] | None = None,
) -> str | None:
    """Return the next unused tool from the full kill-chain rotation."""
    skip = tried | (failed or set())
    for name in FULL_TOOL_ROTATION:
        if name in allow and name not in skip:
            return name
    for name in sorted(allow):
        if name not in skip:
            return name
    return None


def list_methods(
    *,
    posture: str | Posture | None = None,
    phase: str | None = None,
) -> list[dict[str, Any]]:
    p = normalize_posture(str(posture) if posture is not None else None)
    rows: list[dict[str, Any]] = []
    for entry in METHOD_CATALOG:
        if phase and entry.get("phase") != phase:
            continue
        if p == "defensive" and entry.get("risk") == "high":
            continue
        rows.append(dict(entry))
    return rows


def list_technique_families() -> dict[str, list[str]]:
    """Merge WAF evasion + SQLi technique inventories."""
    from tools.sql_injection import list_techniques as sqli_techniques
    from tools.waf_evasion import list_techniques as waf_techniques

    return {
        "waf_evasion": waf_techniques(),
        "sql_injection": sqli_techniques(),
        "dark_web": list_dark_web_methods(),
    }


def list_dark_web_methods() -> dict[str, list[str]]:
    from tools.dark_web import list_dark_web_methods as _list

    return _list()


# Parallel scaffold/* bundles for aggressive auto-execute and adaptive escalation.
AGGRESSIVE_SCAFFOLD_STRIKES: tuple[str, ...] = (
    "scaffold/full-surface-strike",
    "scaffold/waf-bypass-strike",
    "scaffold/api-endpoint-strike",
    "scaffold/sqli-impact-strike",
    "scaffold/xss-chain-strike",
    "scaffold/ssrf-strike-chain",
    "scaffold/cred-spray-strike",
    "scaffold/ad-domain-strike",
    "scaffold/cloud-misconfig-strike",
)

PROFILE_SCAFFOLD_STRIKES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("wordpress", "cms", "wp-content"), "scaffold/cms-scanner"),
    (("api", "graphql", "rest", "swagger"), "scaffold/api-endpoint-strike"),
    (("cloudflare", "cdn", "waf", "akamai"), "scaffold/waf-bypass-strike"),
    (("sqli", "mysql", "postgres", "mssql", "oracle"), "scaffold/sqli-impact-strike"),
    (("xss", "cross-site"), "scaffold/xss-chain-strike"),
    (("ssrf", "metadata"), "scaffold/ssrf-strike-chain"),
    (("smb", "ldap", "active directory", "kerberoast"), "scaffold/ad-domain-strike"),
    (("login", "auth", "password", "spray"), "scaffold/cred-spray-strike"),
    (("aws", "cloud", "s3", "azure", "gcp"), "scaffold/cloud-misconfig-strike"),
)


def recommend_scaffold_strikes(
    profile: dict[str, Any] | None,
    allow: set[str],
    *,
    tried: set[str],
) -> list[str]:
    """Profile-matched scaffold/* bundles still available on the allowlist."""
    skip = tried
    ordered: list[str] = []
    signals = profile.get("signals") if profile else None
    if signals:
        blob = " ".join(signals).lower()
        for keywords, strike in PROFILE_SCAFFOLD_STRIKES:
            if not any(kw in blob for kw in keywords):
                continue
            if strike in allow and strike not in skip and strike not in ordered:
                ordered.append(strike)
    for strike in AGGRESSIVE_SCAFFOLD_STRIKES:
        if strike in allow and strike not in skip and strike not in ordered:
            ordered.append(strike)
    return ordered


def next_hunt_strike(tried: set[str], allow: set[str]) -> str | None:
    """Next strike in hunt rotation — scaffolds first, then CLI wrappers."""
    for strike in AGGRESSIVE_SCAFFOLD_STRIKES:
        if strike in allow and strike not in tried:
            return strike
    for name in FULL_TOOL_ROTATION:
        if name in allow and name not in tried:
            return name
    return None


def compile_aggressive_scaffold_opening(
    allow: set[str],
    *,
    max_strikes: int = 3,
) -> dict[str, Any] | None:
    """Opening parallel scaffold strike phase for hunt/adaptive chat compile."""
    strikes = [s for s in AGGRESSIVE_SCAFFOLD_STRIKES if s in allow][:max_strikes]
    if not strikes:
        return None
    return {
        "name": "scaffold_strike",
        "parallel": True,
        "tools": [{"tool": strike, "args": []} for strike in strikes],
    }


def compile_aggressive_tool_list(allow: set[str]) -> list[str]:
    """All allowlisted tools in kill-chain order for chat/mission compile."""
    out: list[str] = []
    for name in FULL_TOOL_ROTATION:
        if name in allow and name not in out:
            out.append(name)
    for name in sorted(allow):
        if name not in out:
            out.append(name)
    return out


_DB_ACCESS_NON_SQLMAP: tuple[dict[str, Any], ...] = (
    {
        "id": "nuclei_sqli",
        "tool": "nuclei",
        "label": "Nuclei SQLi/injection templates",
        "args": ["-tags", "sqli,injection", "-severity", "critical,high,medium", "-silent"],
    },
    {
        "id": "nuclei_exposure",
        "tool": "nuclei",
        "label": "Exposed backups and DB misconfigs",
        "args": [
            "-tags",
            "exposure,misconfig,backup,config",
            "-severity",
            "critical,high,medium",
            "-silent",
        ],
    },
    {
        "id": "ffuf_db_paths",
        "tool": "ffuf",
        "label": "Database admin and dump path fuzzing",
        "args": [
            "-w",
            "/usr/share/dirb/wordlists/common.txt",
            "-ac",
            "-fc",
            "404",
            "-e",
            ".sql,.bak,.dump,.zip,.env,.config",
        ],
    },
    {
        "id": "katana_forms",
        "tool": "katana",
        "label": "Crawl forms and parameters for SQLi",
        "args": ["-d", "3", "-jc", "-kf", "all", "-ef", "css,woff,png,jpg,gif,svg"],
    },
    {
        "id": "httpx_probe",
        "tool": "httpx",
        "label": "Live HTTP probe for injectable endpoints",
        "args": ["-silent", "-status-code", "-title", "-tech-detect", "-follow-redirects"],
    },
)


def wants_database_access(
    nl_goal: str = "",
    *,
    profile: dict[str, Any] | None = None,
    decision_state: dict[str, Any] | None = None,
) -> bool:
    """True when the mission should keep rotating database-access methods."""
    blob = (nl_goal or "").lower()
    if any(
        token in blob
        for token in (
            "database",
            "dbms",
            "sql",
            "sqli",
            "mysql",
            "postgres",
            "mssql",
            "oracle",
            "data dump",
            "db access",
            "get into",
        )
    ):
        return True
    state = decision_state or {}
    if state.get("sql_injection") or state.get("sql_dbms"):
        return True
    signals = set((profile or {}).get("signals") or [])
    return bool(
        signals
        & {
            "sqli",
            "mysql",
            "postgres",
            "mssql",
            "oracle",
            "mongo",
            "login",
            "api",
            "php",
        }
    )


def next_db_access_phase(
    *,
    allow: set[str],
    tried_methods: set[str],
    failed_tools: set[str],
    dbms: str | None,
    step: int,
) -> dict[str, Any] | None:
    """
    Rotate sqlmap argv profiles and companion DB discovery tools until exhausted.
    """
    from tools.sql_injection import next_sqlmap_method

    if "sqlmap" in allow:
        method = next_sqlmap_method(tried=tried_methods, dbms=dbms)
        if method is not None:
            method_id = str(method["id"])
            return {
                "phase_name": f"db_access_{method_id}_s{step}",
                "reason": f"Database access rotation: {method.get('label') or method_id}.",
                "parallel": False,
                "stop": False,
                "tools": [{"tool": "sqlmap", "args": list(method["args"])}],
                "source": "db_access_rotation",
                "db_method_id": method_id,
            }

    for entry in _DB_ACCESS_NON_SQLMAP:
        method_id = str(entry["id"])
        tool = str(entry["tool"])
        if method_id in tried_methods:
            continue
        if tool not in allow:
            continue
        if tool in failed_tools and tool != "sqlmap":
            continue
        return {
            "phase_name": f"db_access_{method_id}_s{step}",
            "reason": f"Database access rotation: {entry.get('label') or method_id}.",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": tool, "args": list(entry["args"])}],
            "source": "db_access_rotation",
            "db_method_id": method_id,
        }
    return None


def compile_aggressive_phases(allow: set[str]) -> list[dict[str, Any]]:
    """Build a full dark-arsenal phase plan from the method catalog."""
    phases: list[dict[str, Any]] = []
    for phase_name in (
        "recon",
        "dark_web",
        "discovery",
        "vuln",
        "creds",
        "windows_ad",
        "postex",
        "exploit",
    ):
        tools: list[dict[str, Any]] = []
        for method in METHOD_CATALOG:
            if method.get("phase") != phase_name:
                continue
            for tool in method.get("tools") or []:
                if tool not in allow or any(t["tool"] == tool for t in tools):
                    continue
                tools.append({"tool": tool, "args": aggressive_args_for(tool)})
        if tools:
            phases.append(
                {
                    "name": phase_name,
                    "parallel": phase_name
                    in {"recon", "dark_web", "discovery", "creds", "windows_ad", "postex"},
                    "tools": tools,
                }
            )
    return phases


def methods_summary_for_llm(
    *,
    posture: str | Posture | None = None,
    allow: set[str] | None = None,
    max_methods: int = 24,
) -> str:
    """Compact black-hat method roster for planner/advisor prompts."""
    p = normalize_posture(str(posture) if posture is not None else None)
    lines = [f"POSTURE={p} authorized attack methods (use allowlist tools only):"]
    count = 0
    for method in METHOD_CATALOG:
        if p == "defensive" and method.get("risk") == "high":
            continue
        tools = [t for t in (method.get("tools") or []) if allow is None or t in allow]
        if not tools:
            continue
        tool_str = ",".join(tools)
        lines.append(f"- [{method['phase']}] {method['name']} → {tool_str}")
        count += 1
        if count >= max_methods:
            break
    if p != "defensive":
        lines.append(
            "Technique families: WAF evasion (encoding, header injection, pollution), "
            "SQLi BEUSTQ, CVE→metasploit auto-chain. OSINT tools (theharvester, darkweb, "
            "breach_intel) scrape public/hidden sources and match leaks to seeds only — "
            "never vuln scans, payloads, or credential attacks."
        )
    try:
        from orchestrator.ai.scaffold_tools import scaffold_summary_for_llm

        lines.append("")
        lines.append(scaffold_summary_for_llm(max_rows=12))
    except Exception:
        pass
    return "\n".join(lines)
