import json


def test_daily_pipeline_gpu_passes_no_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("FIREBREAK_TRAIN_GPU", "true")

    captured: dict[str, object] = {}

    def fake_run_script(rel, extra_argv=None):
        captured["rel"] = rel
        captured["extra_argv"] = list(extra_argv or [])
        return {"ok": True, "returncode": 0, "result": None}

    import orchestrator.ml.auto_train as auto_train

    monkeypatch.setattr(auto_train, "_run_script", fake_run_script)

    result = auto_train.run_daily_pipeline()
    assert result.get("gpu_train") is True
    assert captured["rel"] == "training/scripts/qlora_train.py"
    assert "--no-dry-run" in captured["extra_argv"]
    assert "--include-posture" in captured["extra_argv"]
    assert "--include-community" in captured["extra_argv"]


def test_daily_pipeline_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("FIREBREAK_TRAIN_GPU", raising=False)
    from orchestrator.ml.auto_train import run_daily_pipeline

    result = run_daily_pipeline()
    assert result.get("ok") is True
    assert result.get("gpu_train") is False
    report = tmp_path / "ml" / "daily_report.json"
    assert report.is_file()
    data = json.loads(report.read_text())
    assert "schema_eval" in data or "steps" in data
