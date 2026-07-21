"""Firebreak multi-scaffold consensus + router tests."""

from orchestrator.ai import consensus, scaffolds


def test_pick_best_prefers_more_tools():
    a = {"stop": False, "tools": [{"tool": "nmap"}], "scaffold_id": "a"}
    b = {
        "stop": False,
        "tools": [{"tool": "nmap"}, {"tool": "whatweb"}],
        "scaffold_id": "b",
    }
    best = consensus.pick_best_plan([a, b])
    assert best is not None
    assert len(best["tools"]) == 2


def test_agreement_score_full_and_none():
    a = {"tools": [{"tool": "nmap"}, {"tool": "whatweb"}], "scaffold_id": "a"}
    b = {"tools": [{"tool": "nmap"}, {"tool": "whatweb"}], "scaffold_id": "b"}
    assert consensus.agreement_score([a, b]) == 1.0

    c = {"tools": [{"tool": "ffuf"}], "scaffold_id": "c"}
    assert consensus.agreement_score([a, c]) == 0.0

    # Single candidate = full agreement by convention.
    assert consensus.agreement_score([a]) == 1.0


def test_summarize_consensus_partial_overlap():
    a = {"tools": [{"tool": "nmap"}, {"tool": "whatweb"}], "scaffold_id": "primary"}
    b = {"tools": [{"tool": "nmap"}, {"tool": "ffuf"}], "scaffold_id": "fallback"}
    summary = consensus.summarize_consensus([a, b])
    assert summary["candidates"] == 2
    # Jaccard: intersection {nmap}=1, union {nmap,whatweb,ffuf}=3 -> 0.333
    assert 0.3 < summary["confidence"] < 0.34
    assert set(summary["sources"]) == {"primary", "fallback"}
    assert summary["tools_by_scaffold"]["primary"] == ["nmap", "whatweb"]


def test_high_agreement_prefers_pick_best_semantics():
    """When scaffolds agree, pick_best should keep the richer tool list."""
    a = {"stop": False, "tools": [{"tool": "nmap"}], "scaffold_id": "a"}
    b = {
        "stop": False,
        "tools": [{"tool": "nmap"}, {"tool": "whatweb"}],
        "scaffold_id": "b",
    }
    summary = consensus.summarize_consensus([a, b])
    # Jaccard: {nmap}/{nmap,whatweb} = 0.5 — below 0.7 merge threshold
    assert summary["confidence"] == 0.5
    agreed = [
        {"stop": False, "tools": [{"tool": "nmap"}, {"tool": "whatweb"}], "scaffold_id": "a"},
        {"stop": False, "tools": [{"tool": "nmap"}, {"tool": "whatweb"}], "scaffold_id": "b"},
    ]
    assert consensus.summarize_consensus(agreed)["confidence"] == 1.0
    best = consensus.pick_best_plan(agreed)
    assert best is not None
    assert len(best["tools"]) == 2


def test_merge_tool_lists_dedupes():
    a = {"tools": [{"tool": "nmap", "args": []}], "scaffold_id": "a"}
    b = {
        "tools": [{"tool": "nmap", "args": ["-sV"]}, {"tool": "ffuf", "args": []}],
        "scaffold_id": "b",
    }
    merged = consensus.merge_tool_lists(a, b)
    names = [t["tool"] for t in merged["tools"]]
    assert names == ["nmap", "ffuf"]


def test_multi_scaffold_flag(monkeypatch):
    monkeypatch.setenv("FIREBREAK_MULTI_SCAFFOLD", "true")
    assert scaffolds.multi_scaffold_enabled() is True
    monkeypatch.setenv("FIREBREAK_MULTI_SCAFFOLD", "false")
    assert scaffolds.multi_scaffold_enabled() is False


def test_default_scaffolds_include_fallback(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("FIREBREAK_LLM_MODEL", "firebreak")
    monkeypatch.setenv("FIREBREAK_LLM_BASE_MODEL", "qwen2.5:7b")
    rows = scaffolds.default_scaffolds()
    ids = {r["id"] for r in rows}
    assert "ollama-primary" in ids
    assert "ollama-fallback" in ids
