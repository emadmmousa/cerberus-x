"""Fix flaky enqueue unit test."""

import json

import pytest

from orchestrator.mcp import actions, sessions
from orchestrator.tasks import run_nmap_task, run_sqlmap_task


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    sessions.reset_memory_store()
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "true")
    monkeypatch.setattr(sessions, "_redis", lambda: None)


@pytest.fixture
def authz_file(tmp_path, monkeypatch):
    path = tmp_path / "authorized_targets.json"
    path.write_text(
        json.dumps({"targets": [{"target": "authorized.example", "authorized": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    return path


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


def test_enqueue_tool_denies_off_list_target(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    sid = sessions.create_session("offlist.example")["session_id"]
    enqueued = False

    def fake_delay(*args, **kwargs):
        nonlocal enqueued
        enqueued = True

    monkeypatch.setattr(run_nmap_task, "delay", fake_delay)

    with pytest.raises(PermissionError, match="authorized-target"):
        actions.enqueue_tool(
            session_id=sid, tool="nmap", target="offlist.example"
        )

    assert enqueued is False


def test_enqueue_tool_checks_requested_worker_task(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    sid = sessions.create_session("authorized.example")["session_id"]
    enqueued = False

    def fake_delay(*args, **kwargs):
        nonlocal enqueued
        enqueued = True

    monkeypatch.setattr(run_nmap_task, "delay", fake_delay)
    monkeypatch.setattr(
        actions,
        "assert_workers_ready",
        lambda names: (_ for _ in ()).throw(RuntimeError("stale")),
    )

    with pytest.raises(RuntimeError, match="stale"):
        actions.enqueue_tool(
            session_id=sid, tool="nmap", target="authorized.example"
        )

    assert enqueued is False
