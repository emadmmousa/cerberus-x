"""AI memory must stay scoped to the mission host."""

from orchestrator.ai import memory


def test_normalize_target_hint_strips_scheme_and_www():
    assert memory.normalize_target_hint("https://www.DistroKid.com/") == "distrokid.com"
    assert memory.normalize_target_hint("distrokid.com") == "distrokid.com"


def test_recall_does_not_leak_other_targets(monkeypatch, tmp_path):
    db = tmp_path / "mem.db"
    monkeypatch.setenv("FIREBREAK_DB_PATH", str(db))
    memory.init_memory_db()

    memory.remember("goal=Inject database phases=['ai_recon']", target_hint="https://www.takwene.com")
    memory.remember("goal=recon only", target_hint="https://www.distrokid.com/")

    hits = memory.recall(
        "https://www.distrokid.com/ inject database",
        k=5,
        target_hint="https://www.distrokid.com/",
    )
    assert hits
    assert all("takwene" not in (h["summary"] + (h["target_hint"] or "")).lower() for h in hits)
    assert all(memory.normalize_target_hint(h["target_hint"]) == "distrokid.com" for h in hits)


def test_recall_without_hint_still_returns_rows(monkeypatch, tmp_path):
    db = tmp_path / "mem2.db"
    monkeypatch.setenv("FIREBREAK_DB_PATH", str(db))
    memory.init_memory_db()
    memory.remember("goal=a", target_hint="https://a.example")
    memory.remember("goal=b", target_hint="https://b.example")
    hits = memory.recall("goal", k=5)
    assert len(hits) == 2
