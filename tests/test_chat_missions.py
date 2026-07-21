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
        lambda messages, parse_failures=0: {
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
        json={"content": "Scan lab.example.com"},
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
