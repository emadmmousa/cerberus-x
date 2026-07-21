from orchestrator import database


def test_normalize_list_of_tool_dicts():
    rows = database._normalize_phase_outputs(
        [{"tool": "nmap", "ports": [{"port": "80"}]}]
    )
    assert rows == [("nmap", {"tool": "nmap", "ports": [{"port": "80"}]})]


def test_normalize_single_tool_dict():
    rows = database._normalize_phase_outputs(
        {"tool": "sqlmap", "vulnerable": False}
    )
    assert rows == [("sqlmap", {"tool": "sqlmap", "vulnerable": False})]


def test_normalize_legacy_mapping():
    rows = database._normalize_phase_outputs({"nmap": {"ports": []}})
    assert rows == [("nmap", {"ports": []})]


def test_save_single_dict_action_output(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path / "output"))
    database.init_db()
    database.save_phase_result(
        "https://example.com",
        "auto_sqlmap_exploitation",
        {"tool": "sqlmap", "vulnerable": False},
    )
    rows = database.get_results("https://example.com")
    assert len(rows) == 1
    assert rows[0]["tool"] == "sqlmap"


def test_get_results_filters_by_job_id(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path / "output"))
    database.init_db()
    database.save_phase_result(
        "takwene.com",
        "recon",
        [{"tool": "nmap", "ports": [{"port": "80"}]}],
        job_id="job-old",
    )
    database.save_phase_result(
        "takwene.com",
        "recon",
        [{"tool": "nmap", "ports": [{"port": "443"}]}],
        job_id="job-new",
    )

    all_rows = database.get_results("takwene.com")
    assert len(all_rows) == 2

    scoped = database.get_results("takwene.com", job_id="job-new")
    assert len(scoped) == 1
    assert scoped[0]["job_id"] == "job-new"
    assert scoped[0]["result"]["ports"][0]["port"] == "443"

    empty = database.get_results("takwene.com", job_id="missing")
    assert empty == []
