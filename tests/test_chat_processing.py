"""Tests for chat processing persistence."""

from __future__ import annotations

from unittest.mock import patch


def _client():
    from orchestrator import dashboard

    return dashboard.app.test_client()


def test_get_chat_clears_stale_processing():
    client = _client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    from orchestrator.chat import store as chat_store

    thread = chat_store.get_chat(chat_id)
    assert thread is not None
    thread["processing"] = True
    thread["processing_started_at"] = 0
    chat_store.save_chat(thread)

    resp = client.get(f"/api/chat/missions/{chat_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("processing") is False


def test_stream_sets_and_clears_processing():
    client = _client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]

    with patch("orchestrator.chat.intake.try_cerberus_command", return_value="quick reply"):
        with patch(
            "orchestrator.chat.intake.detect_proposal",
            return_value={"ready": False, "target": "", "posture": "aggressive"},
        ):
            with patch(
                "orchestrator.chat.intake.sync_reply_for_proposal",
                return_value="quick reply",
            ):
                resp = client.post(
                    f"/api/chat/missions/{chat_id}/stream",
                    json={"content": "menu"},
                )
                _ = resp.data

    assert resp.status_code == 200
    from orchestrator.chat import store as chat_store

    thread = chat_store.get_chat(chat_id)
    assert thread is not None
    assert thread.get("processing") is False
    assert any(m.get("role") == "assistant" for m in thread.get("messages") or [])


def test_stream_rejects_concurrent_requests():
    client = _client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    from orchestrator.chat import store as chat_store

    thread = chat_store.get_chat(chat_id)
    assert thread is not None
    chat_store.set_processing(thread, processing=True)

    resp = client.post(
        f"/api/chat/missions/{chat_id}/stream",
        json={"content": "hello again"},
    )
    assert resp.status_code == 409
    assert resp.get_json().get("processing") is True
