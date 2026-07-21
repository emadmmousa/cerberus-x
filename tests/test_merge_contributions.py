"""merge_contributions script smoke tests."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "merge_contributions.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("merge_contributions", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["merge_contributions"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_contribution_to_messages_shape():
    mc = _load_module()
    row = mc.contribution_to_messages(
        {
            "id": "abc",
            "prompt": "q",
            "response": "a",
            "license": "CC-BY-4.0",
            "source": "community",
            "posture": "aggressive",
        }
    )
    assert row["messages"][0]["role"] == "system"
    assert "posture=aggressive" in row["messages"][0]["content"]
    assert row["messages"][1]["content"] == "q"
    assert row["messages"][2]["content"] == "a"
    assert row["meta"]["id"] == "abc"
    assert row["meta"]["posture"] == "aggressive"


def test_merge_dry_run(tmp_path, monkeypatch, capsys):
    mc = _load_module()
    contrib = tmp_path / "contributions.jsonl"
    contrib.write_text(
        json.dumps(
            {
                "prompt": "What is MFA?",
                "response": "Multi-factor authentication reduces account takeover.",
                "license": "CC-BY-4.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mc, "CONTRIB_PATHS", [contrib])
    monkeypatch.setattr(mc, "SEED", tmp_path / "seed.jsonl")
    monkeypatch.setattr(sys, "argv", ["merge_contributions.py"])
    assert mc.main() == 0
    out = capsys.readouterr().out
    assert "unique contributions: 1" in out
    assert "dry-run" in out
