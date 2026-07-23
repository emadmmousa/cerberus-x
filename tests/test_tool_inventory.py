"""Tool inventory + arsenal API tests."""

from tools import inventory
from orchestrator import dashboard
from orchestrator.mcp import registry
from orchestrator.tasks import _TASK_MAP


def test_catalog_matches_task_map():
    from orchestrator.ai.scaffold_tools import EXPECTED_SCAFFOLD_COUNT

    names = {entry["name"] for entry in inventory.TOOL_CATALOG}
    wired = set(_TASK_MAP.keys())
    assert names == wired
    scaffolds = [n for n in names if n.startswith("scaffold/")]
    assert len(scaffolds) == EXPECTED_SCAFFOLD_COUNT


def test_probe_marks_metasploit_ready_without_binary():
    entry = inventory.catalog_by_name()["metasploit"]
    row = inventory.probe_local_tool(entry)
    assert row["ready"] is True
    assert row["status"] == "framework"


def test_registry_descriptors_include_categories():
    from orchestrator.ai.scaffold_tools import EXPECTED_SCAFFOLD_COUNT

    tools = registry.list_tool_descriptors()
    wired = len(_TASK_MAP)
    assert len(tools) >= wired
    assert all("category" in t for t in tools)
    scaffold_desc = [t for t in tools if str(t.get("name", "")).startswith("scaffold/")]
    assert len(scaffold_desc) == EXPECTED_SCAFFOLD_COUNT
    high = registry.list_tool_descriptors(category="high")
    assert "sqlmap" in {t["name"] for t in high}
    assert "nmap" not in {t["name"] for t in high}


def test_api_tools_lists_wired_wrappers():
    from orchestrator.ai.scaffold_tools import EXPECTED_SCAFFOLD_COUNT

    client = dashboard.app.test_client()
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    data = resp.get_json()
    wired = len(_TASK_MAP)
    assert data["count"] == 41
    assert data["wired_count"] == wired
    assert data["scaffold_count"] == EXPECTED_SCAFFOLD_COUNT
    names = {t["name"] for t in data["tools"]}
    assert "nmap" in names
    assert len(data.get("scaffolds") or []) == EXPECTED_SCAFFOLD_COUNT


def test_api_tools_health_enqueue(monkeypatch):
    class FakeAsync:
        id = "health-1"
        state = "PENDING"

    monkeypatch.setattr(
        "orchestrator.tasks.run_tools_health_task.delay",
        lambda: FakeAsync(),
    )
    client = dashboard.app.test_client()
    resp = client.get("/api/tools/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["task_id"] == "health-1"
    assert data["state"] == "PENDING"
