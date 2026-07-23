"""Scaffold virtual tools and expanded aggressive arsenal tests."""

from __future__ import annotations

from orchestrator.ai.scaffold_catalog import cyber_scaffold_catalog
from orchestrator.ai.scaffold_tools import (
    EXPECTED_SCAFFOLD_COUNT,
    assert_all_scaffolds_wired,
    expand_phase_tools,
    get_scaffold_registry,
    is_scaffold_tool,
    scaffold_tool_name,
    scaffold_tool_names,
    tools_for_scaffold,
)
from orchestrator.mcp.registry import known_tools
from orchestrator.tasks import _TASK_MAP, build_phase_workflow, run_scaffold_bundle_task
from tools.inventory import CLI_TOOL_CATALOG, TOOL_CATALOG, scaffold_inventory_rows
from tools.wrappers import scaffold_bundle


def test_scaffold_catalog_has_160_specialists():
    assert len(cyber_scaffold_catalog()) == EXPECTED_SCAFFOLD_COUNT
    assert len(scaffold_tool_names()) == EXPECTED_SCAFFOLD_COUNT
    assert_all_scaffolds_wired()


def test_all_scaffolds_in_task_map_and_inventory():
    scaffolds = scaffold_tool_names()
    assert len(scaffolds) == EXPECTED_SCAFFOLD_COUNT
    assert scaffolds <= set(_TASK_MAP.keys())
    inventory_scaffolds = {
        row["name"] for row in TOOL_CATALOG if row.get("maturity") == "scaffold"
    }
    assert inventory_scaffolds == scaffolds
    assert len(CLI_TOOL_CATALOG) == 41
    assert len(TOOL_CATALOG) == 41 + EXPECTED_SCAFFOLD_COUNT


def test_every_scaffold_maps_to_task_map_entry():
    for name in scaffold_tool_names():
        assert _TASK_MAP[name] is run_scaffold_bundle_task


def test_sql_injection_scaffold_bundle():
    bundle = tools_for_scaffold("sql-injection")
    assert "sqlmap" in bundle
    assert "nuclei" in bundle
    assert len(get_scaffold_registry()["sql-injection"]) >= 2


def test_expand_phase_tools_keeps_scaffold_wrappers_by_default():
    phase = [{"tool": "scaffold/port-scan", "args": []}]
    expanded = expand_phase_tools(phase)
    assert len(expanded) == 1
    assert expanded[0]["tool"] == "scaffold/port-scan"


def test_expand_phase_tools_can_flatten_when_requested():
    phase = [{"tool": "scaffold/nuclei-runner", "args": []}]
    expanded = expand_phase_tools(phase, expand_scaffolds=True)
    assert expanded == [{"tool": "nuclei", "args": ["-t", "http/cves/", "-severity", "critical,high", "-silent"]}]


def test_known_tools_includes_all_scaffolds():
    allow = known_tools()
    assert "nmap" in allow
    assert scaffold_tool_name("tool-orchestrator") in allow
    assert len([n for n in allow if n.startswith("scaffold/")]) == EXPECTED_SCAFFOLD_COUNT


def test_catalog_matches_task_map():
    assert {entry["name"] for entry in TOOL_CATALOG} == set(_TASK_MAP.keys())


def test_build_phase_workflow_schedules_scaffold_wrapper():
    workflow = build_phase_workflow(
        "scaffold_test",
        [{"tool": "scaffold/nuclei-runner", "args": []}],
        "https://example.com",
        parallel=True,
    )
    assert workflow is not None


def test_scaffold_inventory_rows_count():
    rows = scaffold_inventory_rows()
    assert len(rows) == EXPECTED_SCAFFOLD_COUNT


def test_scaffold_bundle_wrapper_runs_child_tools(monkeypatch):
    calls: list[str] = []

    def fake_nuclei(target, args=None, evasion=None):
        calls.append("nuclei")
        return {"tool": "nuclei", "target": target, "productive": True}

    monkeypatch.setitem(scaffold_bundle._SCANNERS, "nuclei", ("fake", "scan"))
    monkeypatch.setattr(scaffold_bundle, "_runner", lambda name: fake_nuclei if name == "nuclei" else None)

    result = scaffold_bundle.scan("https://example.com", scaffold_id="nuclei-runner")
    assert result["tool"] == "scaffold/nuclei-runner"
    assert result["scaffold_id"] == "nuclei-runner"
    assert calls == ["nuclei"]
