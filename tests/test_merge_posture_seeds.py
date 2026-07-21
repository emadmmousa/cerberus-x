"""merge_posture_seeds script smoke tests."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "training" / "scripts" / "merge_posture_seeds.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("merge_posture_seeds", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["merge_posture_seeds"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_contribution_to_messages_includes_posture():
    mc = _load_module()
    row = mc.contribution_to_messages(
        {
            "id": "agg-001",
            "prompt": "q",
            "response": "a",
            "license": "Apache-2.0",
            "source": "aggressive_seed",
            "posture": "aggressive",
        }
    )
    assert "posture=aggressive" in row["messages"][0]["content"]
    assert row["meta"]["posture"] == "aggressive"
    assert row["meta"]["id"] == "agg-001"


def test_merge_posture_dry_run(tmp_path, monkeypatch, capsys):
    mc = _load_module()
    agg = tmp_path / "aggressive_examples.jsonl"
    agg.write_text(
        json.dumps(
            {
                "id": "agg-001",
                "posture": "aggressive",
                "source": "aggressive_seed",
                "prompt": "Authorized aggressive recon.",
                "response": '{"phase_name":"ai_recon","tools":[{"tool":"nmap","args":[]}],"stop":false}',
                "license": "Apache-2.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    defn = tmp_path / "defensive_examples.jsonl"
    defn.write_text(
        json.dumps(
            {
                "id": "def-001",
                "posture": "defensive",
                "source": "defensive_seed",
                "prompt": "Authorized defensive exposure check.",
                "response": "Prefer nuclei and nmap; do not schedule sqlmap.",
                "license": "Apache-2.0",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mc, "POSTURE_PATHS", [agg, defn])
    monkeypatch.setattr(mc, "SEED", tmp_path / "seed.jsonl")
    monkeypatch.setattr(mc, "V0", tmp_path / "v0")
    monkeypatch.setattr(sys, "argv", ["merge_posture_seeds.py"])
    assert mc.main() == 0
    out = capsys.readouterr().out
    assert "unique posture examples: 2" in out
    assert "dry-run" in out
