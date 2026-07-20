"""AI mission runner safety filter tests."""

from celery.exceptions import TimeoutError as CeleryTimeoutError

from orchestrator.ai.runner import run_ai_mission


def test_runner_skips_high_risk_without_confirm(monkeypatch):
    monkeypatch.setenv("CERBERUS_AI_REQUIRE_CONFIRM", "true")
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


def test_runner_continues_after_phase_timeout(monkeypatch):
    plans = [
        {
            "phase_name": "Reconnaissance",
            "tools": [{"tool": "nmap", "args": ["-T4"]}],
            "parallel": True,
            "stop": False,
            "reason": "recon",
            "source": "llm",
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

    class FakeAsync:
        id = "grp-1"
        children = []

        def revoke(self, **_k):
            return None

        def successful(self):
            return False

    class FakeWorkflow:
        def apply_async(self):
            return FakeAsync()

    monkeypatch.setattr("orchestrator.ai.planner.suggest_next_phase", fake_plan)
    monkeypatch.setattr(
        "orchestrator.tasks.build_phase_workflow", lambda *a, **k: FakeWorkflow()
    )
    monkeypatch.setattr(
        "orchestrator.ai.runner.collect_group_results",
        lambda *_a, **_k: (_ for _ in ()).throw(
            CeleryTimeoutError("The operation timed out.")
        ),
    )
    monkeypatch.setattr("orchestrator.ai.runner.save_phase_result", lambda *a, **k: None)
    monkeypatch.setattr(
        "orchestrator.ai.runner.DecisionEngine",
        lambda *a, **k: type("DE", (), {"evaluate_phase": lambda *x, **y: None})(),
    )
    monkeypatch.setattr("orchestrator.ai.memory.remember", lambda *a, **k: 1)

    job = {}
    logs = []
    run_ai_mission(
        job=job,
        job_id="j2",
        target="example.com",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=True,
        max_steps=3,
        add_log=logs.append,
    )
    assert any("timed out" in m for m in logs)
    assert job.get("results", {}).get("Reconnaissance")
    assert job["ai"].get("finished_at")
