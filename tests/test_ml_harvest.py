import json
from pathlib import Path


def test_harvest_completed_mission_once(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path))
    from orchestrator.job_store import playbook_jobs
    from orchestrator.ml.harvest import run_learning_tick, HARVESTED_KEY
    from utils.redis_utils import get_redis

    r = get_redis()
    try:
        r.delete(HARVESTED_KEY)
    except Exception:
        pass

    # Stored via job store API; harvest enumerates via list_summaries (local + Redis).
    job_id = "job-harvest-1"
    playbook_jobs[job_id] = {
        "task_id": job_id,
        "state": "SUCCESS",
        "target": "https://lab.example",
        "ai_mode": True,
        "posture": "balanced",
        "nl_goal": "authorized recon",
        "results": {
            "ai_recon": [{"tool": "nmap", "ports": [{"port": 443}]}],
        },
    }

    try:
        out1 = run_learning_tick()
        assert out1["harvested"] >= 1
        path = Path(out1["path"])
        assert path.is_file()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert any(job_id in line or "lab.example" in line for line in lines)

        out2 = run_learning_tick()
        assert out2["harvested"] == 0
        assert out2.get("skipped_dup", 0) >= 1
    finally:
        playbook_jobs._local.pop(job_id, None)
        try:
            r.delete(HARVESTED_KEY)
        except Exception:
            pass
