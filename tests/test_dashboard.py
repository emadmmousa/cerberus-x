from pathlib import Path
from types import SimpleNamespace

from orchestrator import dashboard
from orchestrator.dashboard import STATIC_APP, app


def test_dashboard_serves_spa_when_built():
    client = app.test_client()
    spa_index = STATIC_APP / "index.html"

    response = client.get("/")

    assert response.status_code == 200
    if spa_index.is_file():
        html = response.get_data(as_text=True)
        assert 'id="root"' in html
        assert "FIREBREAK" in html.upper()
    else:
        # Fallback Jinja template during development without a frontend build
        html = response.get_data(as_text=True)
        assert "FIREBREAK" in html.upper()


def test_auto_exploit_session_runs_post_exploitation_actions(monkeypatch, tmp_path):
    from orchestrator import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    requested_tools = []
    outputs = [
        [
            {
                "tool": "nuclei",
                "findings": [
                    {
                        "title": "CVE-2021-41773 Path Traversal",
                        "severity": "critical",
                    }
                ],
            }
        ],
        [{"tool": "metasploit", "sessions": [{"id": "42", "type": "meterpreter"}]}],
        [{"tool": "metasploit"}],
        [{"tool": "metasploit"}],
        [{"tool": "metasploit"}],
    ]

    class FakeWorkflow:
        def apply_async(self):
            return SimpleNamespace(id=f"task-{len(requested_tools)}")

    def fake_build_phase_workflow(_phase, tools, *_args, **_kwargs):
        requested_tools.append(tools)
        return FakeWorkflow()

    monkeypatch.setattr(dashboard, "build_phase_workflow", fake_build_phase_workflow)
    monkeypatch.setattr(dashboard, "save_phase_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        dashboard, "collect_chain_results", lambda *_args, **_kwargs: outputs.pop(0)
    )
    job_id = "exploit-session-job"
    dashboard.playbook_jobs[job_id] = {"phases": []}
    playbook = {
        "phases": [
            {
                "name": "vulnerability_scan",
                "tools": [{"tool": "nuclei", "args": []}],
            }
        ]
    }

    dashboard._run_playbook_job(job_id, "example.com", playbook)

    post_ex_tools = [
        tool
        for request in requested_tools
        for tool in request
        if tool["args"] and tool["args"][0].startswith("post/")
    ]
    assert dashboard.playbook_jobs[job_id]["state"] == "SUCCESS", dashboard.playbook_jobs[
        job_id
    ].get("error")
    assert len(post_ex_tools) == 3
    assert all("SESSION=42" in tool["args"] for tool in post_ex_tools)


def test_post_phase_action_is_not_dispatched_after_cancellation_race(monkeypatch):
    dispatched: list[str] = []
    job_id = "cancel-race-job"
    dashboard.playbook_jobs[job_id] = {"phases": []}

    class FakeWorkflow:
        def __init__(self, name: str):
            self.name = name

        def apply_async(self):
            dispatched.append(self.name)
            return SimpleNamespace(id=f"{self.name}-task")

    def fake_build_phase_workflow(name, *_args, **_kwargs):
        if name.startswith("auto_"):
            cancelled = dict(dashboard.playbook_jobs[job_id])
            cancelled["cancel_requested"] = True
            dashboard.playbook_jobs[job_id] = cancelled
        return FakeWorkflow(name)

    class FakeDecisionEngine:
        state = {"has_session": False}

        def __init__(self, *_args, **_kwargs):
            pass

        def should_run_phase(self, _phase):
            return True, ""

        def evaluate_phase(self, *_args, **_kwargs):
            return None

        def generate_post_phase_actions(self, *_args, **_kwargs):
            return [{"phase": "auto_followup", "tool": "nuclei", "args": []}]

        def mark_actions_fired(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(dashboard, "DecisionEngine", FakeDecisionEngine)
    monkeypatch.setattr(dashboard, "build_phase_workflow", fake_build_phase_workflow)
    monkeypatch.setattr(dashboard, "collect_chain_results", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(dashboard, "save_phase_result", lambda *_args, **_kwargs: None)

    dashboard._run_playbook_job(
        job_id,
        "example.test",
        {"phases": [{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}]},
    )

    assert dispatched == ["recon"]
    assert dashboard.playbook_jobs[job_id]["state"] == "CANCELLED"


def test_playbook_does_not_start_when_cancelled_before_thread_entry(monkeypatch):
    job_id = "cancel-before-playbook-start"
    dashboard.playbook_jobs[job_id] = {
        "phases": [],
        "state": "CANCEL_REQUESTED",
        "cancel_requested": True,
    }
    monkeypatch.setattr(
        dashboard,
        "build_phase_workflow",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not schedule")),
    )

    dashboard._run_playbook_job(
        job_id,
        "example.test",
        {"phases": [{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}]},
    )

    assert dashboard.playbook_jobs[job_id]["state"] == "CANCELLED"


def test_post_exploitation_action_is_not_dispatched_after_cancellation_race(monkeypatch):
    dispatched: list[str] = []
    job_id = "post-exploitation-cancel-race"
    dashboard.playbook_jobs[job_id] = {"phases": []}

    class FakeWorkflow:
        def __init__(self, name: str):
            self.name = name

        def apply_async(self):
            dispatched.append(self.name)
            return SimpleNamespace(id=f"{self.name}-task")

    def fake_build_phase_workflow(name, *_args, **_kwargs):
        if name == "post_exploitation":
            cancelled = dict(dashboard.playbook_jobs[job_id])
            cancelled["cancel_requested"] = True
            dashboard.playbook_jobs[job_id] = cancelled
        return FakeWorkflow(name)

    class FakeDecisionEngine:
        state = {"has_session": True}

        def __init__(self, *_args, **_kwargs):
            self.action_calls = 0

        def should_run_phase(self, _phase):
            return True, ""

        def evaluate_phase(self, *_args, **_kwargs):
            return None

        def generate_post_phase_actions(self, *_args, **_kwargs):
            self.action_calls += 1
            if self.action_calls == 2:
                return [{"phase": "post_exploitation", "tool": "metasploit", "args": []}]
            return []

        def mark_actions_fired(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(dashboard, "DecisionEngine", FakeDecisionEngine)
    monkeypatch.setattr(dashboard, "build_phase_workflow", fake_build_phase_workflow)
    monkeypatch.setattr(dashboard, "collect_chain_results", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(dashboard, "save_phase_result", lambda *_args, **_kwargs: None)

    dashboard._run_playbook_job(
        job_id,
        "example.test",
        {"phases": [{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}]},
    )

    assert dispatched == ["recon"]
    assert dashboard.playbook_jobs[job_id]["state"] == "CANCELLED"


def test_playbook_finalizes_late_cancel_requested_state(monkeypatch):
    job_id = "late-dashboard-cancel"
    dashboard.playbook_jobs[job_id] = {"phases": []}

    class FakeWorkflow:
        def apply_async(self):
            return SimpleNamespace(id="recon-task")

    class FakeDecisionEngine:
        state = {"has_session": False}

        def __init__(self, *_args, **_kwargs):
            pass

        def should_run_phase(self, _phase):
            return True, ""

        def evaluate_phase(self, *_args, **_kwargs):
            cancelled = dict(dashboard.playbook_jobs[job_id])
            cancelled["state"] = "CANCEL_REQUESTED"
            dashboard.playbook_jobs[job_id] = cancelled

        def generate_post_phase_actions(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(dashboard, "DecisionEngine", FakeDecisionEngine)
    monkeypatch.setattr(dashboard, "build_phase_workflow", lambda *_args, **_kwargs: FakeWorkflow())
    monkeypatch.setattr(dashboard, "collect_chain_results", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(dashboard, "save_phase_result", lambda *_args, **_kwargs: None)

    dashboard._run_playbook_job(
        job_id,
        "example.test",
        {"phases": [{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}]},
    )

    assert dashboard.playbook_jobs[job_id]["state"] == "CANCELLED"


def test_playbook_exception_keeps_cancellation_terminal(monkeypatch):
    job_id = "dashboard-cancelled-exception"
    dashboard.playbook_jobs[job_id] = {"phases": []}

    class FakeWorkflow:
        def apply_async(self):
            return SimpleNamespace(id="recon-task")

    def fail_collection(*_args, **_kwargs):
        cancelled = dict(dashboard.playbook_jobs[job_id])
        cancelled.update(
            state="CANCEL_REQUESTED",
            cancel_requested=True,
        )
        dashboard.playbook_jobs[job_id] = cancelled
        raise RuntimeError("collection failed")

    monkeypatch.setattr(dashboard, "build_phase_workflow", lambda *_args, **_kwargs: FakeWorkflow())
    monkeypatch.setattr(dashboard, "collect_chain_results", fail_collection)

    dashboard._run_playbook_job(
        job_id,
        "example.test",
        {"phases": [{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}]},
    )

    assert dashboard.playbook_jobs[job_id]["state"] == "CANCELLED"
