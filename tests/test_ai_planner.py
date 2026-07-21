"""AI planner and memory tests."""

import os

import pytest

from orchestrator.ai import memory, planner
from orchestrator.ai.safety import require_confirm_for_tool


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("FIREBREAK_DB_PATH", str(db))
    monkeypatch.delenv("FIREBREAK_LLM_BASE_URL", raising=False)


def test_heuristic_initial_plan():
    plan = planner.suggest_next_phase("https://www.example.com", {}, step=0)
    assert plan["source"] == "heuristic"
    assert plan["stop"] is False
    names = {t["tool"] for t in plan["tools"]}
    assert "nmap" in names or "rustscan" in names


def test_heuristic_prefers_sqli_from_nl_goal():
    prior = {
        "ai_recon": [
            {"tool": "nmap", "ports": [{"port": "443", "state": "open"}]},
            {"tool": "nuclei", "findings": []},
            {"tool": "nikto", "issues": []},
            {"tool": "ffuf", "results": []},
        ]
    }
    plan = planner.suggest_next_phase(
        "example.com",
        prior,
        nl_goal="prefer SQL injection",
        step=1,
    )
    # After vuln tools done, sqli goal should surface sqlmap
    assert plan["stop"] is False
    assert any(t["tool"] == "sqlmap" for t in plan["tools"])


def test_memory_roundtrip():
    memory.remember("used nuclei then sqlmap successfully", "example.com")
    hits = memory.recall("sqlmap nuclei example.com", k=2)
    assert hits
    assert "sqlmap" in hits[0]["summary"]


def test_completions_url_normalization():
    from orchestrator.ai import llm

    assert (
        llm.completions_url("http://ollama:11434/v1")
        == "http://ollama:11434/v1/chat/completions"
    )
    assert (
        llm.completions_url("http://ollama:11434")
        == "http://ollama:11434/v1/chat/completions"
    )
    assert llm.completions_url("") is None


def test_llm_masscan_args_get_sanitized(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")

    def fake_chat(messages, **_k):
        return (
            '{"phase_name":"Reconnaissance","reason":"scan","parallel":true,'
            '"stop":false,"tools":[{"tool":"masscan","args":["-sV","--limit=1000","-p1-1024"]}]}'
        )

    monkeypatch.setattr("orchestrator.ai.llm.chat_completion", fake_chat)
    plan = planner.suggest_next_phase("https://example.com", {}, step=0)
    assert plan["source"] == "llm"
    mass = next(t for t in plan["tools"] if t["tool"] == "masscan")
    assert "-sV" not in mass["args"]
    assert not any(a.startswith("--limit") for a in mass["args"])


def test_llm_plan_drops_completed_and_duplicate_tools(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")

    def fake_chat(messages, **_k):
        return (
            '{"phase_name":"ai_recon","reason":"again","parallel":true,"stop":false,'
            '"tools":['
            '{"tool":"masscan","args":["-p80,443"]},'
            '{"tool":"masscan","args":["-p80,443,22"]},'
            '{"tool":"nmap","args":["-sV","-p80,443"]}'
            "]}"
        )

    monkeypatch.setattr("orchestrator.ai.llm.chat_completion", fake_chat)
    prior = {
        "ai_recon": [
            {"tool": "masscan", "ports": [{"port": "80"}, {"port": "443"}]},
            {"tool": "whatweb", "raw_output": "ok"},
        ]
    }
    plan = planner.suggest_next_phase("https://example.com", prior, step=1)
    assert plan["source"] == "llm"
    names = [t["tool"] for t in plan["tools"]]
    assert "masscan" not in names
    assert names.count("nmap") == 1
    assert plan["phase_name"].endswith("_s1")


def test_llm_empty_after_filter_stops(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")

    def fake_chat(messages, **_k):
        return (
            '{"phase_name":"ai_recon","reason":"again","parallel":true,"stop":false,'
            '"tools":[{"tool":"nmap","args":["-sV"]}]}'
        )

    monkeypatch.setattr("orchestrator.ai.llm.chat_completion", fake_chat)
    prior = {"ai_recon": [{"tool": "nmap", "ports": [{"port": "443"}]}]}
    plan = planner.suggest_next_phase("https://example.com", prior, step=1)
    assert plan["stop"] is True
    assert plan["tools"] == []


def test_high_risk_confirm_gate(monkeypatch):
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "true")
    assert require_confirm_for_tool("sqlmap") is True
    assert require_confirm_for_tool("nmap") is False
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "false")
    assert require_confirm_for_tool("sqlmap") is False
