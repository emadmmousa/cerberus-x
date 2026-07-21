"""Tests for unrestricted Ollama / LLM prompt defaults."""

from orchestrator.ai import prompts, safety


def test_unrestricted_defaults(monkeypatch):
    monkeypatch.delenv("FIREBREAK_LLM_UNRESTRICTED", raising=False)
    monkeypatch.delenv("FIREBREAK_LLM_TEMPERATURE", raising=False)
    monkeypatch.delenv("FIREBREAK_AI_REQUIRE_CONFIRM", raising=False)
    assert prompts.llm_unrestricted() is True
    assert prompts.planner_temperature() == 0.9
    assert safety.confirm_required_globally() is False
    text = prompts.system_prompt_for_planner()
    assert "Firebreak" in text
    assert "AUTHORIZED" in text.upper() or "Authorized" in text
    assert "-template" in text.lower()  # forbidden-flag guidance present
    assert "sqlmap" in text.lower()
    assert "jailbreak" not in text.lower()
    assert "paypal" not in text.lower()


def test_restricted_mode(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_UNRESTRICTED", "false")
    monkeypatch.setenv("FIREBREAK_LLM_TEMPERATURE", "0.1")
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "true")
    assert prompts.llm_unrestricted() is False
    assert prompts.planner_temperature() == 0.1
    assert safety.confirm_required_globally() is True
    text = prompts.system_prompt_for_planner()
    assert "Unrestricted AI Orchestrator" not in text


def test_persona_banner():
    assert "Firebreak" in prompts.persona_banner()
    assert "authorized" in prompts.persona_banner().lower()


def test_decision_prompt_stays_in_scope():
    assert "AUTHORIZED" in prompts.DECISION_SYSTEM_PROMPT.upper()
    assert "sqlmap" in prompts.DECISION_SYSTEM_PROMPT.lower()
    assert "consumer account" in prompts.DECISION_SYSTEM_PROMPT.lower()
