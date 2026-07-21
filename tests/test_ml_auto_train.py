import json


def test_daily_pipeline_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("CERBERUS_TRAIN_GPU", raising=False)
    from orchestrator.ml.auto_train import run_daily_pipeline

    result = run_daily_pipeline()
    assert result.get("ok") is True
    assert result.get("gpu_train") is False
    report = tmp_path / "ml" / "daily_report.json"
    assert report.is_file()
    data = json.loads(report.read_text())
    assert "schema_eval" in data or "steps" in data
