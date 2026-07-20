"""Tests for MCP sessions, auth, and registry."""

import pytest

from orchestrator.mcp import auth, registry, sessions


@pytest.fixture(autouse=True)
def _clean_memory(monkeypatch):
    sessions.reset_memory_store()
    monkeypatch.setenv("CERBERUS_MCP_API_KEY", "test-key")
    monkeypatch.setenv("CERBERUS_AI_REQUIRE_CONFIRM", "true")
    monkeypatch.setattr(sessions, "_redis", lambda: None)


def test_create_and_get_session():
    created = sessions.create_session("https://example.com", label="lab")
    assert created["session_id"]
    loaded = sessions.get_session(created["session_id"])
    assert loaded["target"] == "https://example.com"


def test_rate_limit(monkeypatch):
    monkeypatch.setenv("CERBERUS_MCP_RATE_LIMIT_PER_MIN", "2")
    sid = sessions.create_session("t.com")["session_id"]
    assert sessions.check_rate_limit(sid) is True
    assert sessions.check_rate_limit(sid) is True
    assert sessions.check_rate_limit(sid) is False


def test_api_key_auth(monkeypatch):
    from flask import Flask, request

    app = Flask(__name__)
    monkeypatch.setenv("CERBERUS_MCP_API_KEY", "secret")
    with app.test_request_context(headers={"X-API-Key": "secret"}):
        assert auth.require_api_key(request) is None
    with app.test_request_context(headers={"X-API-Key": "wrong"}):
        resp = auth.require_api_key(request)
        assert resp[1] == 401


def test_list_tools_includes_nmap():
    names = {t["name"] for t in registry.list_tool_descriptors()}
    assert "nmap" in names
    assert "metasploit" in names
    high = {t["name"] for t in registry.list_tool_descriptors(category="high")}
    assert "metasploit" in high
    assert "nmap" not in high
