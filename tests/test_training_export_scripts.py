"""export_gguf / merge_adapter script smoke tests."""

import importlib.util
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


def test_export_gguf_write_modelfile(tmp_path):
    mod = _load("export_gguf", ROOT / "training" / "scripts" / "export_gguf.py")
    gguf = tmp_path / "firebreak-q4.gguf"
    gguf.write_bytes(b"fake")
    out = tmp_path / "Modelfile.firebreak-gguf"
    path = mod.write_modelfile(gguf=gguf, out=out, name="firebreak")
    text = path.read_text(encoding="utf-8")
    assert "FROM" in text
    assert "SYSTEM" in text
    assert "Firebreak" in text or "authorized" in text.lower()


def test_merge_adapter_dry_run(capsys):
    mod = _load("merge_adapter", ROOT / "training" / "scripts" / "merge_adapter.py")
    monkey_argv = ["merge_adapter.py"]
    old = sys.argv
    sys.argv = monkey_argv
    try:
        assert mod.main() == 0
    finally:
        sys.argv = old
    out = capsys.readouterr().out
    assert "dry-run" in out
