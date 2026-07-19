from orchestrator import database as db


def test_state_is_isolated_per_job(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "state.db"))
    db.init_db()
    db.save_state("takwene.com", {"vuln_found": True}, job_id="job-a")
    db.save_state("takwene.com", {"vuln_found": False}, job_id="job-b")
    assert db.load_state("takwene.com", job_id="job-a")["vuln_found"] is True
    assert db.load_state("takwene.com", job_id="job-b")["vuln_found"] is False
    assert db.load_state("takwene.com") == {}
