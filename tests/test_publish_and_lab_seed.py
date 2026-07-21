"""publish_dataset / lab seed honesty smoke tests."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_card_is_honest_on_repo_card():
    mod = _load("publish_dataset", ROOT / "training" / "scripts" / "publish_dataset.py")
    ok, msg = mod.card_is_honest(ROOT / "training" / "dataset" / "DATASET_CARD.md")
    assert ok, msg


def test_card_is_honest_rejects_csi_claim(tmp_path):
    mod = _load("publish_dataset", ROOT / "training" / "scripts" / "publish_dataset.py")
    bad = tmp_path / "CARD.md"
    bad.write_text("Our model beats CSI on every benchmark.\n", encoding="utf-8")
    ok, msg = mod.card_is_honest(bad)
    assert not ok
    assert "beats csi" in msg


def test_publish_dry_run_exits_zero(capsys):
    mod = _load("publish_dataset", ROOT / "training" / "scripts" / "publish_dataset.py")
    old = sys.argv
    sys.argv = ["publish_dataset.py"]
    try:
        assert mod.main() == 0
    finally:
        sys.argv = old
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "card honesty" in out


def test_lab_seed_build_wrappers_only():
    mod = _load("generate_lab_seed", ROOT / "training" / "scripts" / "generate_lab_seed.py")
    rows = mod.build()
    assert len(rows) >= 5
    knowledge = 0
    for row in rows:
        user = json.loads(row["messages"][1]["content"])
        assistant = json.loads(row["messages"][-1]["content"])
        if user.get("task") == "security_knowledge":
            knowledge += 1
            answer = (assistant.get("answer") or "").lower()
            assert answer.startswith("no")
            continue
        for item in assistant.get("tools") or []:
            assert item["tool"] in mod.ALLOW, item
    assert knowledge >= 2
