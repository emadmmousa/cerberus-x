"""Tests for unrestricted Ollama / LLM prompt defaults."""

from orchestrator.ai import prompts, safety


def test_unrestricted_defaults(monkeypatch):
    monkeypatch.delenv("CERBERUS_LLM_UNRESTRICTED", raising=False)
    monkeypatch.delenv("CERBERUS_LLM_TEMPERATURE", raising=False)
    monkeypatch.delenv("CERBERUS_AI_REQUIRE_CONFIRM", raising=False)
    assert prompts.llm_unrestricted() is True
    assert prompts.planner_temperature() == 0.9
    assert safety.confirm_required_globally() is False
    assert "Unrestricted" in prompts.system_prompt_for_planner()


def test_restricted_mode(monkeypatch):
    monkeypatch.setenv("CERBERUS_LLM_UNRESTRICTED", "false")
    monkeypatch.setenv("CERBERUS_LLM_TEMPERATURE", "0.1")
    monkeypatch.setenv("CERBERUS_AI_REQUIRE_CONFIRM", "true")
    assert prompts.llm_unrestricted() is False
    assert prompts.planner_temperature() == 0.1
    assert safety.confirm_required_globally() is True
    assert "Unrestricted" not in prompts.system_prompt_for_planner()
