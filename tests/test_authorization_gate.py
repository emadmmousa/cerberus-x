"""Authorized-target gate: dict-format parsing + launch enforcement."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def authz_file(tmp_path, monkeypatch):
    data = {
        "targets": [
            {"target": "wks.agency", "authorized": True, "expiry": "2099-12-31T23:59:59"},
            {"target": "revoked.example", "authorized": False},
            {"target": "expired.example", "authorized": True, "expiry": "2000-01-01T00:00:00"},
            "plainstring.example",
        ]
    }
    path = tmp_path / "authorized_targets.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    return path


def test_parses_dict_targets_and_www_variants(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    from scanner import AuthorizationEnforcer as A

    assert A.check("wks.agency") is True
    assert A.check("https://www.wks.agency/path") is True
    assert A.check("plainstring.example") is True


def test_rejects_unauthorized_expired_and_offlist(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    from scanner import AuthorizationEnforcer as A

    assert A.check("distrokid.com") is False
    assert A.check("revoked.example") is False
    assert A.check("expired.example") is False


def test_disabled_gate_allows_everything(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "false")
    from scanner import AuthorizationEnforcer as A

    assert A.check("anything-goes.example") is True


def test_launch_denies_unauthorized_target(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    from orchestrator import dashboard
    from orchestrator.chat import store as cs

    client = dashboard.app.test_client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    thread = cs.get_chat(chat_id)
    # Force a ready draft aimed at an out-of-scope host.
    cs.set_draft(
        thread,
        {
            "target": "distrokid.com",
            "posture": "aggressive",
            "nl_goal": "unauthorized",
            "stealth": "high",
            "ready": True,
        },
    )
    resp = client.post(f"/api/chat/missions/{chat_id}/launch", json={})
    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json().get("reason") == "unauthorized_target"


def test_launch_allows_authorized_target(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    from orchestrator import dashboard
    from orchestrator.api import chat_missions
    from orchestrator.chat import store as cs

    captured: dict = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return {"task_id": "job-1", "target": kwargs["target"], "state": "PENDING", "ai_mode": True}

    monkeypatch.setattr(chat_missions, "_start_mission", fake_start)

    client = dashboard.app.test_client()
    chat_id = client.post("/api/chat/missions").get_json()["chat_id"]
    thread = cs.get_chat(chat_id)
    cs.set_draft(
        thread,
        {
            "target": "wks.agency",
            "posture": "aggressive",
            "nl_goal": "authorized",
            "stealth": "high",
            "ready": True,
            "plan": {
                "phases": [
                    {"name": "recon", "parallel": True, "tools": [{"tool": "nmap", "args": ["-sV"]}]}
                ],
                "new_tools": [],
                "tool_names": ["nmap"],
            },
        },
    )
    resp = client.post(f"/api/chat/missions/{chat_id}/launch", json={})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert captured["target"] == "wks.agency"
    assert captured["seed_plan"], "authorized launch should seed the chat plan"
