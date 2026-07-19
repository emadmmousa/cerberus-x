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
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path / "output"))
    database.init_db()
    database.save_phase_result(
        "https://example.com",
        "auto_sqlmap_exploitation",
        {"tool": "sqlmap", "vulnerable": False},
    )
    rows = database.get_results("https://example.com")
    assert len(rows) == 1
    assert rows[0]["tool"] == "sqlmap"
