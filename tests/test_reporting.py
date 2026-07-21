import json

from orchestrator import database
from orchestrator.reporting import export_target_reports, target_filename


def test_target_filename_uses_safe_target_url():
    assert target_filename("https://takwene.com") == "takwene.com"
    assert target_filename("https://example.com/admin/login?q=1") == (
        "example.com_admin_login_q_1"
    )
    assert target_filename("192.0.2.10") == "192.0.2.10"


def test_export_target_reports_writes_json_and_html(tmp_path):
    rows = [
        {
            "target": "https://takwene.com",
            "phase": "recon",
            "tool": "nmap",
            "timestamp": "2026-07-18 20:00:00",
            "result": {
                "tool": "nmap",
                "ports": [{"port": "443", "state": "open", "service": "https"}],
                "raw_output": "<script>alert('unsafe')</script>",
            },
        }
    ]

    paths = export_target_reports(
        "https://takwene.com",
        rows,
        output_dir=tmp_path,
    )

    assert paths["json"] == tmp_path / "takwene.com.json"
    assert paths["html"] == tmp_path / "takwene.com.html"

    report = json.loads(paths["json"].read_text())
    assert report["target"] == "https://takwene.com"
    assert report["phases"]["recon"][0]["tool"] == "nmap"
    assert report["phases"]["recon"][0]["result"]["ports"][0]["port"] == "443"

    html = paths["html"].read_text()
    assert "takwene.com" in html
    assert "nmap" in html
    assert "&lt;script&gt;" in html
    assert "<script>alert" not in html


def test_saving_phase_automatically_refreshes_target_report(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path / "output"))
    database.init_db()

    database.save_phase_result(
        "https://takwene.com",
        "recon",
        [{"tool": "nmap", "ports": [{"port": "443", "state": "open"}]}],
    )

    json_path = tmp_path / "output" / "takwene.com.json"
    html_path = tmp_path / "output" / "takwene.com.html"
    assert json_path.exists()
    assert html_path.exists()
    report = json.loads(json_path.read_text())
    assert report["phases"]["recon"][0]["tool"] == "nmap"
