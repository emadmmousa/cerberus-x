"""Aggressive scaffold strike rotation for adaptive missions."""

from orchestrator.ai.scaffold_tools import EXPECTED_SCAFFOLD_COUNT, scaffold_tool_name
from tools.attack_methods import (
    AGGRESSIVE_SCAFFOLD_STRIKES,
    compile_aggressive_scaffold_opening,
    next_hunt_strike,
    recommend_scaffold_strikes,
)


def test_aggressive_scaffold_strikes_registered():
    for strike in AGGRESSIVE_SCAFFOLD_STRIKES:
        sid = strike.replace("scaffold/", "")
        assert scaffold_tool_name(sid) == strike
    assert len(AGGRESSIVE_SCAFFOLD_STRIKES) == 9


def test_compile_aggressive_scaffold_opening():
    allow = set(AGGRESSIVE_SCAFFOLD_STRIKES) | {"nmap"}
    phase = compile_aggressive_scaffold_opening(allow, max_strikes=3)
    assert phase is not None
    assert phase["parallel"] is True
    assert len(phase["tools"]) == 3
    assert all(t["tool"].startswith("scaffold/") for t in phase["tools"])


def test_next_hunt_strike_prefers_scaffolds():
    allow = set(AGGRESSIVE_SCAFFOLD_STRIKES) | {"nmap", "nuclei"}
    first = next_hunt_strike(set(), allow)
    assert first == AGGRESSIVE_SCAFFOLD_STRIKES[0]
    second = next_hunt_strike({first}, allow)
    assert second == AGGRESSIVE_SCAFFOLD_STRIKES[1]


def test_recommend_scaffold_strikes_by_profile():
    allow = set(AGGRESSIVE_SCAFFOLD_STRIKES) | {scaffold_tool_name("cms-scanner")}
    strikes = recommend_scaffold_strikes(
        {"signals": ["api", "graphql"]},
        allow,
        tried=set(),
    )
    assert strikes[0] == "scaffold/api-endpoint-strike"


def test_catalog_count_includes_strike_scaffolds():
    assert EXPECTED_SCAFFOLD_COUNT == 160
