from orchestrator.ai import scaffolds


def test_default_scaffold_is_firebreak(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("FIREBREAK_LLM_MODEL", "firebreak")
    monkeypatch.setenv("FIREBREAK_LLM_BASE_MODEL", "qwen2.5:7b")
    rows = scaffolds.list_enabled()
    assert any(r["model"] == "firebreak" for r in rows)
    assert any(r["id"] == "ollama-primary" for r in rows)


def test_disabled_without_base_url(monkeypatch):
    monkeypatch.delenv("FIREBREAK_LLM_BASE_URL", raising=False)
    assert scaffolds.list_enabled() == []
