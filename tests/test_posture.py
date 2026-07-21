"""Dual posture (aggressive / defensive / balanced) tests."""

from orchestrator.ai.posture import (
    filter_allowlist,
    hardening_recommendations,
    normalize_posture,
)
from orchestrator.ai.prompts import persona_banner, system_prompt_for_planner


def test_normalize_aliases():
    assert normalize_posture("red") == "aggressive"
    assert normalize_posture("blue") == "defensive"
    assert normalize_posture("balanced") == "balanced"
    assert normalize_posture("nope") == "balanced"


def test_defensive_filters_offensive_tools():
    allow = {"nmap", "nuclei", "sqlmap", "metasploit", "nikto"}
    out = filter_allowlist(allow, "defensive")
    assert "sqlmap" not in out
    assert "metasploit" not in out
    assert "nmap" in out
    assert "nuclei" in out


def test_hardening_from_ports():
    recs = hardening_recommendations(
        {
            "p1": [
                {
                    "tool": "nmap",
                    "ports": [{"port": 22}, {"port": 80}],
                }
            ]
        }
    )
    titles = {r["title"] for r in recs}
    assert "Harden SSH" in titles
    assert "Enforce HTTPS" in titles
    assert any("MFA" in r["title"] for r in recs)


def test_prompts_differ_by_posture():
    d = system_prompt_for_planner("defensive")
    a = system_prompt_for_planner("aggressive")
    assert "Defensive" in d or "hardening" in d.lower()
    assert "dual-mode" in a.lower() or "AGGRESSIVE" in a.upper() or "proof-of-impact" in a
    assert "defensive" in persona_banner("defensive").lower()
    assert "balanced" in persona_banner("balanced").lower()
