"""Recommended aggressive chat prompts for the Strike Library UI."""

from __future__ import annotations

from typing import Any

# Mirrors frontend/src/lib/aggressivePrompts.ts — keep in sync when adding prompts.

AGGRESSIVE_CHAT_PROMPTS: list[dict[str, Any]] = [
    {
        "id": "full-arsenal",
        "codename": "DARK ARSENAL",
        "title": "Complete dark arsenal",
        "category": "full",
        "tools": ["rustscan", "nuclei", "sqlmap", "metasploit", "darkweb"],
        "prompt": (
            "Plan and execute a full aggressive red-team on my authorized target: use the "
            "complete dark arsenal (recon, dark web OSINT, discovery, vuln scan, creds, AD "
            "helpers, proof-of-impact). Don't stop until confirmed vulnerabilities."
        ),
    },
    {
        "id": "execute-until-vuln",
        "codename": "NO MERCY",
        "title": "Hunt until confirmed vulns",
        "category": "adaptive",
        "tools": ["nuclei", "ffuf", "sqlmap", "xsstrike", "metasploit"],
        "prompt": (
            "Execute adaptive attack on authorized TARGET — deep surface study, profile-matched "
            "tools, rotate through every allowlisted scanner, invent novel wrappers if standard "
            "tools fail. Hunt until confirmed findings."
        ),
    },
    {
        "id": "darkweb-full",
        "codename": "BLACK MIRROR",
        "title": "Dark web OSINT sweep",
        "category": "darkweb",
        "tools": ["darkweb", "theharvester"],
        "prompt": (
            "Run OSINT only on authorized TARGET and OSINT seeds: darkweb --method full "
            "(onion search, leak hunt, breach correlate, Tor hidden-service probes), "
            "theharvester, and breach_intel. Report leak matches — no exploitation."
        ),
    },
]


def list_chat_prompts(*, posture: str | None = None) -> list[dict[str, Any]]:
    p = (posture or "aggressive").strip().lower()
    if p != "aggressive":
        return []
    return list(AGGRESSIVE_CHAT_PROMPTS)
