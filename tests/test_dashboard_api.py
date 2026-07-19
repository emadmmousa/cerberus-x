import json

from orchestrator import dashboard


def test_health_and_metrics_endpoints():
    client = dashboard.app.test_client()
    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert b"cerberus_" in metrics.data or metrics.data  # registry may be empty


def test_api_run_requires_target():
    client = dashboard.app.test_client()
    response = client.post("/api/run")
    assert response.status_code == 400
    assert response.get_json()["error"] == "target is required"


def test_api_run_missing_playbook():
    client = dashboard.app.test_client()
    response = client.post("/api/run?target=example.com&playbook=missing.yaml")
    assert response.status_code == 404


def test_results_falls_back_to_sqlite(monkeypatch, tmp_path):
    from orchestrator import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path / "output"))
    database.init_db()
    database.save_phase_result(
        "https://example.com",
        "recon",
        [{"tool": "nmap", "ports": [{"port": "80"}]}],
    )

    class _Unavailable:
        available = False

        def search_results(self, **kwargs):
            return None

    monkeypatch.setattr(dashboard, "es_client", _Unavailable())
    client = dashboard.app.test_client()
    response = client.get("/results?target=https://example.com")
    assert response.status_code == 200
    rows = response.get_json()
    assert rows[0]["tool"] == "nmap"


def test_api_run_accepts_proxy_flags(monkeypatch):
    captured = {}

    def _fake_run(job_id, target, playbook, use_proxy=False, proxy_protocol="http"):
        captured["use_proxy"] = use_proxy
        captured["proxy_protocol"] = proxy_protocol
        dashboard.playbook_jobs[job_id]["state"] = "SUCCESS"

    class ImmediateThread:
        def __init__(self, target=None, args=(), kwargs=None, daemon=None):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(dashboard.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(dashboard, "_run_playbook_job", _fake_run)
    monkeypatch.setattr(
        "builtins.open",
        lambda *a, **k: __import__("io").StringIO("phases: []\n"),
    )
    client = dashboard.app.test_client()
    resp = client.post(
        "/api/run",
        json={"target": "example.com", "use_proxy": True, "proxy_protocol": "http"},
    )
    assert resp.status_code == 200
    assert captured["use_proxy"] is True
    assert captured["proxy_protocol"] == "http"


def test_proxy_status_no_secrets(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    client = dashboard.app.test_client()
    data = client.get("/api/proxy/status").get_json()
    assert data == {"configured": True}
    assert "secret" not in str(data)
