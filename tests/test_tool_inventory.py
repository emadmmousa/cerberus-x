"""Tool inventory + arsenal API tests."""

from tools import inventory
from orchestrator import dashboard
from orchestrator.mcp import registry
from orchestrator.tasks import _TASK_MAP


def test_catalog_matches_task_map():
    names = {entry["name"] for entry in inventory.TOOL_CATALOG}
    assert names == set(_TASK_MAP.keys())
    assert len(names) == 23


def test_probe_marks_metasploit_ready_without_binary():
    entry = inventory.catalog_by_name()["metasploit"]
    row = inventory.probe_local_tool(entry)
    assert row["ready"] is True
    assert row["status"] == "framework"


def test_registry_descriptors_include_categories():
    tools = registry.list_tool_descriptors()
    assert len(tools) == 23
    assert all("category" in t for t in tools)
    high = registry.list_tool_descriptors(category="high")
    assert "sqlmap" in {t["name"] for t in high}
    assert "nmap" not in {t["name"] for t in high}


def test_api_tools_lists_wired_wrappers():
    client = dashboard.app.test_client()
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 23
    assert data["wired_count"] == 23
    names = {t["name"] for t in data["tools"]}
    assert names == set(_TASK_MAP.keys())


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
