"""HTTP tests for MCP JSON-RPC endpoint."""

import pytest

from orchestrator.dashboard import app
from orchestrator.mcp import sessions


@pytest.fixture
def client(monkeypatch):
    sessions.reset_memory_store()
    monkeypatch.setenv("FIREBREAK_MCP_API_KEY", "test-key")
    monkeypatch.setenv("FIREBREAK_MCP_ENABLED", "true")
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "true")
    monkeypatch.setattr(sessions, "_redis", lambda: None)
    app.config["TESTING"] = True
    return app.test_client()


def test_mcp_unauthorized(client):
    res = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert res.status_code == 401


def test_mcp_initialize_and_session(client):
    headers = {"X-API-Key": "test-key"}
    res = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert res.status_code == 200
    assert res.get_json()["result"]["serverInfo"]["name"] == "firebreak"

    res = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "session_create",
                "arguments": {"target": "https://example.com"},
            },
        },
    )
    assert res.status_code == 200
    session_id = res.get_json()["result"]["session_id"]

    res = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_tools",
                "arguments": {"session_id": session_id},
            },
        },
    )
    assert res.status_code == 200
    tools = res.get_json()["result"]["tools"]
    assert any(t["name"] == "nmap" for t in tools)


def test_mcp_run_tool_mocked(client, monkeypatch):
    headers = {"X-API-Key": "test-key"}
    sid = sessions.create_session("example.com")["session_id"]

    class FakeAsync:
        id = "celery-1"

    from orchestrator.tasks import run_nmap_task

    monkeypatch.setattr(
        run_nmap_task, "delay", lambda *a, **k: FakeAsync()
    )

    res = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "run_tool",
                "arguments": {
                    "session_id": sid,
                    "tool": "nmap",
                    "target": "example.com",
                    "args": ["-sV"],
                },
            },
        },
    )
    assert res.status_code == 200
    assert res.get_json()["result"]["task_id"] == "celery-1"
