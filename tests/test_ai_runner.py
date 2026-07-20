"""AI mission runner safety filter tests."""

from orchestrator.ai.runner import run_ai_mission


def test_runner_skips_high_risk_without_confirm(monkeypatch):
    plans = [
        {
            "phase_name": "ai_step_0",
            "tools": [{"tool": "sqlmap", "args": {}}],
            "parallel": False,
            "stop": False,
            "reason": "test",
            "source": "heuristic",
        },
        {
            "phase_name": "done",
            "tools": [],
            "parallel": False,
            "stop": True,
            "reason": "done",
            "source": "heuristic",
        },
    ]
    calls = {"n": 0}

    def fake_plan(*_a, **_k):
        i = min(calls["n"], len(plans) - 1)
        calls["n"] += 1
        return plans[i]

    monkeypatch.setattr("orchestrator.ai.planner.suggest_next_phase", fake_plan)
    monkeypatch.setattr(
        "orchestrator.tasks.build_phase_workflow",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not enqueue")),
    )

    job = {}
    logs = []
    run_ai_mission(
        job=job,
        job_id="j1",
        target="example.com",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=False,
        max_steps=3,
        add_log=logs.append,
    )
    assert any("Skipping high-risk" in m for m in logs)
    assert job["ai"]["steps"]
