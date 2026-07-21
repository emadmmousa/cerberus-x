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
