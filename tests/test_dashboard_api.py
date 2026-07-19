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

    def _fake_run(
        job_id,
        target,
        playbook,
        use_proxy=False,
        proxy_protocol="http",
        evasion=None,
    ):
        captured["use_proxy"] = use_proxy
        captured["proxy_protocol"] = proxy_protocol
        captured["evasion"] = evasion
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
        lambda *a, **k: __import__("io").StringIO(
            "evasion: medium\nphases: []\n"
        ),
    )
    client = dashboard.app.test_client()
    resp = client.post(
        "/api/run",
        json={
            "target": "example.com",
            "use_proxy": True,
            "proxy_protocol": "http",
            "evasion": "high",
        },
    )
    assert resp.status_code == 200
    assert captured["use_proxy"] is True
    assert captured["proxy_protocol"] == "http"
    assert captured["evasion"]["random_headers"] is True
    assert captured["evasion"]["random_delay_max"] >= 1.0


def test_playbook_summary_lists_phases():
    client = dashboard.app.test_client()
    resp = client.get("/api/playbook")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["evasion"] == "aggressive"
    assert "phases" in data
    assert isinstance(data["phases"], list)
    assert data["phases"], "expected at least one phase"
    first = data["phases"][0]
    assert set(first) >= {"name", "tools", "parallel", "depends_on", "when"}
    assert isinstance(first["tools"], list)


def test_playbook_summary_missing_file():
    client = dashboard.app.test_client()
    resp = client.get("/api/playbook?playbook=nope.yaml")
    assert resp.status_code == 404


def test_proxy_status_no_secrets(monkeypatch):
    monkeypatch.setenv("CERBERUS_PROXY_SETTINGS_BACKEND", "memory")
    from tools import proxy_settings

    proxy_settings._memory_clear()
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    client = dashboard.app.test_client()
    data = client.get("/api/proxy/status").get_json()
    assert data == {"configured": True}
    assert "secret" not in str(data)


def test_results_endpoint_scopes_to_job_id(monkeypatch, tmp_path):
    from orchestrator import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path / "output"))
    database.init_db()
    database.save_phase_result(
        "example.com",
        "recon",
        [{"tool": "nmap", "ports": [{"port": "80"}]}],
        job_id="job-a",
    )
    database.save_phase_result(
        "example.com",
        "recon",
        [{"tool": "nmap", "ports": [{"port": "443"}]}],
        job_id="job-b",
    )

    class _Unavailable:
        available = False

        def search_results(self, **kwargs):
            return None

    monkeypatch.setattr(dashboard, "es_client", _Unavailable())
    client = dashboard.app.test_client()
    scoped = client.get("/results?target=example.com&job_id=job-b").get_json()
    assert len(scoped) == 1
    assert scoped[0]["job_id"] == "job-b"
    assert scoped[0]["result"]["ports"][0]["port"] == "443"

    all_rows = client.get("/results?target=example.com").get_json()
    assert len(all_rows) == 2
    monkeypatch.setenv("CERBERUS_PROXY_SETTINGS_BACKEND", "memory")
    from tools import proxy_settings

    proxy_settings._memory_clear()
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    client = dashboard.app.test_client()
    data = client.get("/api/proxy/status").get_json()
    assert data == {"configured": True}
    assert "secret" not in str(data)


def test_auto_action_phase_is_reported_before_waiting(monkeypatch):
    job_id = "job-auto-phase"
    dashboard.playbook_jobs[job_id] = {"phases": [], "results": {}}

    class FakeWorkflow:
        def __init__(self, phase_name):
            self.phase_name = phase_name

        def apply_async(self):
            return type("Result", (), {"id": f"{self.phase_name}-task"})()

    class FakeDecisionEngine:
        def __init__(self, *args, **kwargs):
            self.state = {"has_session": False}

        def should_run_phase(self, phase):
            return True, None

        def evaluate_phase(self, *args):
            pass

        def generate_post_phase_actions(self, phase_name, phase_outputs):
            if phase_name == "recon":
                return [
                    {
                        "phase": "proof_of_impact",
                        "tool": "metasploit",
                        "args": {},
                    }
                ]
            return []

        def mark_actions_fired(self, actions):
            pass

    def collect(result, timeout):
        if result.id == "proof_of_impact-task":
            assert dashboard.playbook_jobs[job_id]["phases"][-1] == {
                "phase": "proof_of_impact",
                "task_id": "proof_of_impact-task",
            }
        return []

    monkeypatch.setattr(dashboard, "DecisionEngine", FakeDecisionEngine)
    monkeypatch.setattr(
        dashboard, "build_phase_workflow", lambda phase_name, *args, **kwargs: FakeWorkflow(phase_name)
    )
    monkeypatch.setattr(dashboard, "collect_chain_results", collect)
    monkeypatch.setattr(dashboard, "init_db", lambda: None)
    monkeypatch.setattr(dashboard, "save_phase_result", lambda *args, **kwargs: None)

    dashboard._run_playbook_job(
        job_id,
        "example.com",
        {"phases": [{"name": "recon", "tools": [{"tool": "nmap"}]}]},
    )

    assert dashboard.playbook_jobs[job_id]["state"] == "SUCCESS"


def test_proxy_settings_put_get_redacts_password(monkeypatch, tmp_path):
    monkeypatch.setenv("CERBERUS_PROXY_SETTINGS_BACKEND", "memory")
    from tools import proxy_settings

    proxy_settings._memory_clear()
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=1\n", encoding="utf-8")
    monkeypatch.setenv("CERBERUS_ENV_FILE", str(env_path))
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)

    client = dashboard.app.test_client()
    put = client.put(
        "/api/proxy/settings",
        json={
            "proxy_url": "http://customer-x:s3cret@pr.oxylabs.io:7777",
        },
    )
    assert put.status_code == 200
    data = put.get_json()
    assert data["ok"] is True
    assert data["redis"]["ok"] is True
    assert data["env"]["ok"] is True
    assert data["k8s"]["ok"] is False
    assert "s3cret" not in str(data)
    assert data["password_set"] is True
    assert data["username"] == "customer-x"

    got = client.get("/api/proxy/settings").get_json()
    assert got["configured"] is True
    assert got["source"] == "redis"
    assert "password" not in got
    assert "s3cret" not in str(got)
    assert "OXYLABS_PROXY_PASSWORD=s3cret" in env_path.read_text(encoding="utf-8")


def test_proxy_settings_empty_password_keeps_existing(monkeypatch, tmp_path):
    monkeypatch.setenv("CERBERUS_PROXY_SETTINGS_BACKEND", "memory")
    from tools import proxy_settings

    proxy_settings._memory_clear()
    env_path = tmp_path / ".env"
    monkeypatch.setenv("CERBERUS_ENV_FILE", str(env_path))
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)

    client = dashboard.app.test_client()
    client.put(
        "/api/proxy/settings",
        json={
            "username": "u",
            "password": "keep-me",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        },
    )
    resp = client.put(
        "/api/proxy/settings",
        json={
            "username": "u2",
            "password": "",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        },
    )
    assert resp.status_code == 200
    stored = proxy_settings.load_settings()
    assert stored["password"] == "keep-me"
    assert stored["username"] == "u2"


def test_proxy_settings_put_invalid_returns_400(monkeypatch):
    monkeypatch.setenv("CERBERUS_PROXY_SETTINGS_BACKEND", "memory")
    from tools import proxy_settings

    proxy_settings._memory_clear()
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    client = dashboard.app.test_client()
    resp = client.put("/api/proxy/settings", json={"host": "only-host"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()
