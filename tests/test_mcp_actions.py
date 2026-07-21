"""Fix flaky enqueue unit test."""

import pytest

from orchestrator.mcp import actions, sessions
from orchestrator.tasks import run_nmap_task, run_sqlmap_task


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    sessions.reset_memory_store()
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "true")
    monkeypatch.setattr(sessions, "_redis", lambda: None)


def test_enqueue_nmap_ok(monkeypatch):
    sid = sessions.create_session("example.com")["session_id"]

    class FakeAsync:
        id = "task-nmap"

    monkeypatch.setattr(run_nmap_task, "delay", lambda *a, **k: FakeAsync())
    out = actions.enqueue_tool(
        session_id=sid, tool="nmap", target="example.com", args=["-sV"]
    )
    assert out["task_id"] == "task-nmap"


def test_enqueue_sqlmap_requires_confirm(monkeypatch):
    sid = sessions.create_session("example.com")["session_id"]

    class FakeAsync:
        id = "task-sql"

    monkeypatch.setattr(run_sqlmap_task, "delay", lambda *a, **k: FakeAsync())
    with pytest.raises(PermissionError):
        actions.enqueue_tool(
            session_id=sid, tool="sqlmap", target="example.com", confirm=False
        )
    out = actions.enqueue_tool(
        session_id=sid, tool="sqlmap", target="example.com", confirm=True
    )
    assert out["task_id"] == "task-sql"
