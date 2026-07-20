"""Tool registry metadata for MCP list_tools."""

from __future__ import annotations

from typing import Any

from orchestrator.tasks import _TASK_MAP

HIGH_RISK = frozenset(
    {
        "metasploit",
        "sqlmap",
        "hydra",
        "hashcat",
        "john",
        "impacket",
        "crackmapexec",
        "responder",
        "bloodhound",
        "sliver",
        "winpeas",
        "linpeas",
    }
)

_DESCRIPTIONS = {
    "nmap": "Service/version port scan",
    "masscan": "Fast SYN port discovery",
    "rustscan": "Fast port discovery",
    "zmap": "Internet-scale port sweep helper",
    "whatweb": "Web technology fingerprint",
    "gobuster": "Directory/path discovery",
    "ffuf": "Web content fuzzing",
    "theharvester": "OSINT emails/hosts",
    "nuclei": "Template vulnerability scan",
    "nikto": "Web server misconfiguration scan",
    "xsstrike": "XSS probe",
    "sqlmap": "SQL injection testing",
    "metasploit": "Exploit / post-exploitation modules",
    "hydra": "Online login guessing",
    "john": "Offline hash cracking",
    "hashcat": "GPU/CPU hash cracking",
    "impacket": "Windows protocol attacks",
    "crackmapexec": "Network auth spray / enum",
    "responder": "LLMNR/NBT-NS poisoning helper",
    "bloodhound": "AD path collection helper",
    "sliver": "C2 payload helper",
    "winpeas": "Windows privilege escalation enum",
    "linpeas": "Linux privilege escalation enum",
}


def list_tool_descriptors(category: str | None = None) -> list[dict[str, Any]]:
    tools = []
    for name in sorted(_TASK_MAP.keys()):
        risk = "high" if name in HIGH_RISK else "low"
        if category == "high" and risk != "high":
            continue
        if category == "low" and risk != "low":
            continue
        tools.append(
            {
                "name": name,
                "description": _DESCRIPTIONS.get(name, f"Cerberus tool: {name}"),
                "risk": risk,
                "parameters_schema": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "use_proxy": {"type": "boolean"},
                        "proxy_protocol": {"type": "string"},
                        "confirm": {
                            "type": "boolean",
                            "description": "Required for high-risk tools when confirm mode is on",
                        },
                    },
                    "required": ["target"],
                },
            }
        )
    return tools


def known_tools() -> set[str]:
    return set(_TASK_MAP.keys())
