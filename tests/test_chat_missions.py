"""Mission chat agent: Redis thread store + intake LLM tests."""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _clean_chat_keys(monkeypatch):
    from utils.redis_utils import get_redis
    from orchestrator.chat import store as chat_store
    from security import admin_store

    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "false")
    try:
        admin_store.set_rbac_enforce(False)
    except Exception:
        pass
    monkeypatch.setattr(
        "security.rbac.rbac_enforce_enabled", lambda: False, raising=False
    )

    r = get_redis()
    for key in list(getattr(r, "_data", {}) or {}):
        if str(key).startswith(chat_store.KEY_PREFIX):
            r.delete(key)
    try:
        for key in r.scan_iter(f"{chat_store.KEY_PREFIX}*"):
            r.delete(key)
    except Exception:
        pass
    yield


def test_create_and_get_chat_thread():
    from orchestrator.chat import store as chat_store

    chat_id = chat_store.create_chat(org_id="default")
    assert chat_id
    thread = chat_store.get_chat(chat_id)
    assert thread is not None
    assert thread["org_id"] == "default"
    assert thread["messages"] == []
    assert thread.get("draft") is None


def test_intake_heuristic_extracts_target_without_llm(monkeypatch):
    from orchestrator.chat import intake

    monkeypatch.setattr(intake, "chat_completion", lambda *a, **k: None)
    out = intake.run_intake(
        [{"role": "user", "content": "Scan https://lab.example.com for XSS"}],
        parse_failures=0,
    )
    assert out["proposal"]["target"]
    assert "lab.example.com" in out["proposal"]["target"]
    assert out["proposal"]["ready"] is True


def test_intake_asks_when_no_target(monkeypatch):
    from orchestrator.chat import intake

    monkeypatch.setattr(intake, "chat_completion", lambda *a, **k: None)
    out = intake.run_intake(
        [{"role": "user", "content": "run a balanced mission"}],
        parse_failures=0,
    )
    assert out["proposal"]["ready"] is False
    assert "target" in out["proposal"]["missing"]


def test_intake_soft_fallback_after_retries(monkeypatch):
    from orchestrator.chat import intake

    monkeypatch.setattr(intake, "chat_completion", lambda *a, **k: "not-json")
    out = intake.run_intake(
        [{"role": "user", "content": "hmm"}],
        parse_failures=3,
    )
    assert "Manual" in out["reply"] or "manual" in out["reply"].lower()


def _client():
    from orchestrator import dashboard

    return dashboard.app.test_client()


def test_api_create_message_launch(monkeypatch):
    from orchestrator.chat import intake

    monkeypatch.setattr(
        intake,
        "run_intake",
        lambda messages, parse_failures=0, osint_seeds=None, **kwargs: {
            "reply": "Ready to launch against lab.example.com.",
            "proposal": {
                "target": "lab.example.com",
                "posture": "balanced",
                "nl_goal": "authorized recon",
                "stealth": "high",
                "ready": True,
                "missing": [],
            },
        },
    )

    # Avoid starting real mission threads — stub create path.
    from orchestrator.api import chat_missions as cm

    monkeypatch.setattr(
        cm,
        "_start_mission",
        lambda **kwargs: {"task_id": "job-chat-1", "target": kwargs["target"], "state": "PENDING"},
    )

    c = _client()
    r = c.post("/api/chat/missions")
    assert r.status_code == 201
    chat_id = r.get_json()["chat_id"]

    r = c.post(
        f"/api/chat/missions/{chat_id}/messages",
        json={
            "content": "Scan lab.example.com",
            "options": {"auto_run": False},
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["proposal"]["ready"] is True
    assert data["draft"]["ready"] is True

    r = c.post(f"/api/chat/missions/{chat_id}/launch", json={})
    assert r.status_code == 200
    assert r.get_json()["task_id"] == "job-chat-1"

    r = c.get(f"/api/chat/missions/{chat_id}")
    assert r.status_code == 200
    thread = r.get_json()
    assert thread["draft"] is None
    assert "job-chat-1" in thread["mission_ids"]


def test_non_stream_message_auto_launches_ready_proposal(monkeypatch):
    from orchestrator.api import chat_missions as cm
    from orchestrator.chat import intake

    monkeypatch.setattr(
        intake,
        "run_intake",
        lambda messages, parse_failures=0, osint_seeds=None, **kwargs: {
            "reply": "Launching authorized assessment.",
            "proposal": {
                "target": "lab.example.com",
                "posture": "aggressive",
                "nl_goal": "authorized assessment",
                "stealth": "high",
                "ready": True,
                "missing": [],
            },
        },
    )
    monkeypatch.setattr(
        cm,
        "_start_mission",
        lambda **kwargs: {
            "task_id": "job-auto-1",
            "target": kwargs["target"],
            "state": "PENDING",
        },
    )

    client = _client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    response = client.post(
        f"/api/chat/missions/{chat_id}/messages",
        json={
            "content": "Run an assessment of lab.example.com",
            "options": {"auto_run": True, "always_run": False},
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mission_launched"]["task_id"] == "job-auto-1"
    assert payload["launch_error"] is None
    assert payload["draft"] is None


def test_non_stream_message_respects_auto_run_off(monkeypatch):
    from orchestrator.api import chat_missions as cm
    from orchestrator.chat import intake

    monkeypatch.setattr(
        intake,
        "run_intake",
        lambda messages, parse_failures=0, osint_seeds=None, **kwargs: {
            "reply": "Plan ready.",
            "proposal": {
                "target": "lab.example.com",
                "posture": "aggressive",
                "ready": True,
                "missing": [],
            },
        },
    )
    monkeypatch.setattr(
        cm,
        "_start_mission",
        lambda **kwargs: pytest.fail("Auto Run off must not launch"),
    )

    client = _client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    response = client.post(
        f"/api/chat/missions/{chat_id}/messages",
        json={
            "content": "Run an assessment of lab.example.com",
            "options": {"auto_run": False, "always_run": False},
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mission_launched"] is None
    assert payload["launch_error"] is None
    assert payload["draft"]["ready"] is True


def test_non_stream_auto_launch_preserves_draft_on_authz_denial(monkeypatch):
    from orchestrator.api import chat_missions as cm
    from orchestrator.chat import intake

    monkeypatch.setattr(
        intake,
        "run_intake",
        lambda messages, parse_failures=0, osint_seeds=None, **kwargs: {
            "reply": "Launching.",
            "proposal": {
                "target": "offlist.example",
                "posture": "aggressive",
                "ready": True,
                "missing": [],
            },
        },
    )
    monkeypatch.setattr(
        cm,
        "_start_mission",
        lambda **kwargs: (_ for _ in ()).throw(
            PermissionError("target is not authorized")
        ),
    )

    client = _client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    response = client.post(
        f"/api/chat/missions/{chat_id}/messages",
        json={
            "content": "Run an assessment of offlist.example",
            "options": {"auto_run": True},
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mission_launched"] is None
    assert "not authorized" in payload["launch_error"]
    assert payload["draft"]["target"] == "offlist.example"
