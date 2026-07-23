"""AI mission runner safety filter tests."""

from celery.exceptions import TimeoutError as CeleryTimeoutError
import pytest

from orchestrator.ai.runner import run_ai_mission
from orchestrator.job_store import playbook_jobs
from tests.test_strict_lifecycle_storage import FakeRedis


@pytest.fixture(autouse=True)
def shared_lifecycle_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr("orchestrator.job_store._redis", lambda: redis)
    playbook_jobs._local.clear()
    yield
    playbook_jobs._local.clear()


def seed_lifecycle_job(job_id: str) -> None:
    playbook_jobs[job_id] = {"task_id": job_id, "state": "STARTED", "phases": []}


def test_runner_skips_high_risk_without_confirm(monkeypatch, tmp_path):
    monkeypatch.setenv("FIREBREAK_AI_REQUIRE_CONFIRM", "true")
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr("orchestrator.database.DB_PATH", str(tmp_path / "results.db"))
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
        "orchestrator.ai.runner.build_phase_workflow",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not enqueue")),
    )

    seed_lifecycle_job("j1")
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
        "orchestrator.ai.runner.build_phase_workflow", lambda *a, **k: FakeWorkflow()
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

    seed_lifecycle_job("j2")
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


def test_runner_saves_partial_results_when_collection_raises(monkeypatch):
    plans = [
        {
            "phase_name": "attack",
            "tools": [{"tool": "nuclei", "args": ["-silent"]}],
            "parallel": False,
            "stop": False,
            "reason": "attack",
            "source": "chat_plan",
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
        id = "chain-1"
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
        "orchestrator.ai.runner.build_phase_workflow", lambda *a, **k: FakeWorkflow()
    )
    monkeypatch.setattr(
        "orchestrator.ai.runner.collect_chain_results",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("worker lost")),
    )
    monkeypatch.setattr("orchestrator.ai.runner.save_phase_result", lambda *a, **k: None)
    monkeypatch.setattr(
        "orchestrator.ai.runner.DecisionEngine",
        lambda *a, **k: type("DE", (), {"evaluate_phase": lambda *x, **y: None})(),
    )
    monkeypatch.setattr("orchestrator.ai.memory.remember", lambda *a, **k: 1)

    seed_lifecycle_job("j4")
    job = {}
    logs = []
    run_ai_mission(
        job=job,
        job_id="j4",
        target="example.com",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=True,
        max_steps=3,
        seed_plan=[plans[0]],
        add_log=logs.append,
    )
    assert job.get("results")
    assert any("failed during collection" in m for m in logs)


def test_runner_skips_already_completed_tools(monkeypatch):
    plans = [
        {
            "phase_name": "ai_recon",
            "tools": [
                {"tool": "nmap", "args": ["-sV"]},
                {"tool": "nmap", "args": ["-sV", "-p80"]},
                {"tool": "whatweb", "args": ["-a", "3"]},
            ],
            "parallel": True,
            "stop": False,
            "reason": "recon",
            "source": "llm",
        },
        {
            "phase_name": "ai_recon",
            "tools": [{"tool": "nmap", "args": ["-sV"]}],
            "parallel": True,
            "stop": False,
            "reason": "recon again",
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
    calls = {"n": 0, "enqueued": []}

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
            return True

        @property
        def result(self):
            return [
                {"tool": "nmap", "ports": [{"port": "443"}]},
                {"tool": "whatweb", "raw_output": "ok"},
            ]

    class FakeWorkflow:
        def apply_async(self):
            return FakeAsync()

    def fake_build(phase_name, tools, *_a, **_k):
        calls["enqueued"].append([t["tool"] for t in tools])
        return FakeWorkflow()

    monkeypatch.setattr("orchestrator.ai.planner.suggest_next_phase", fake_plan)
    monkeypatch.setattr("orchestrator.ai.runner.build_phase_workflow", fake_build)
    monkeypatch.setattr(
        "orchestrator.ai.runner.collect_group_results",
        lambda async_result, timeout=None: async_result.result,
    )
    monkeypatch.setattr("orchestrator.ai.runner.save_phase_result", lambda *a, **k: None)
    monkeypatch.setattr(
        "orchestrator.ai.runner.DecisionEngine",
        lambda *a, **k: type("DE", (), {"evaluate_phase": lambda *x, **y: None})(),
    )
    monkeypatch.setattr("orchestrator.ai.memory.remember", lambda *a, **k: 1)

    seed_lifecycle_job("j3")
    job = {}
    logs = []
    run_ai_mission(
        job=job,
        job_id="j3",
        target="example.com",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=True,
        max_steps=5,
        add_log=logs.append,
    )
    # First phase: nmap once + whatweb (intra-plan dedupe).
    assert calls["enqueued"][0] == ["nmap", "whatweb"]
    # Second identical recon plan should be skipped entirely.
    assert any("already-completed" in m or "No new tools" in m for m in logs)
    assert len(calls["enqueued"]) == 1


def test_runner_does_not_dispatch_when_cancelled_after_workflow_build(monkeypatch):
    dispatched: list[str] = []
    job: dict = {}
    playbook_jobs["cancel-before-dispatch"] = job
    job = playbook_jobs["cancel-before-dispatch"]

    class FakeAsync:
        id = "phase-1"
        children = []

    class FakeWorkflow:
        def apply_async(self):
            dispatched.append("phase")
            return FakeAsync()

    def fake_build(*_args, **_kwargs):
        job["cancel_requested"] = True
        authoritative = dict(playbook_jobs["cancel-before-dispatch"])
        authoritative["cancel_requested"] = True
        playbook_jobs["cancel-before-dispatch"] = authoritative
        playbook_jobs.persist("cancel-before-dispatch")
        return FakeWorkflow()

    monkeypatch.setattr("orchestrator.ai.runner.build_phase_workflow", fake_build)
    monkeypatch.setattr("orchestrator.ai.runner.save_phase_result", lambda *_a, **_k: None)
    monkeypatch.setattr("orchestrator.ai.runner.collect_chain_results", lambda *_a, **_k: [])
    monkeypatch.setattr("orchestrator.ai.memory.remember", lambda *_a, **_k: None)

    run_ai_mission(
        job=job,
        job_id="cancel-before-dispatch",
        target="example.test",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=True,
        seed_plan=[{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}],
    )

    assert dispatched == []
    assert job["state"] == "CANCELLED"


def test_runner_revokes_new_group_children_when_cancelled_after_dispatch(monkeypatch):
    job_id = "cancel-after-dispatch"
    playbook_jobs[job_id] = {}
    job = playbook_jobs[job_id]
    revoked: list[str] = []

    class Child:
        def __init__(self, task_id: str):
            self.id = task_id

    class FakeAsync:
        id = "group-1"
        results = [Child("child-1"), Child("child-2")]
        children = []

    class FakeWorkflow:
        def apply_async(self):
            authoritative = dict(playbook_jobs[job_id])
            authoritative.update(cancel_requested=True, state="CANCEL_REQUESTED")
            playbook_jobs[job_id] = authoritative
            return FakeAsync()

    monkeypatch.setattr("orchestrator.ai.runner.build_phase_workflow", lambda *_a, **_k: FakeWorkflow())
    monkeypatch.setattr(
        "celery.result.AsyncResult.revoke",
        lambda self, **_kwargs: revoked.append(self.id),
    )
    monkeypatch.setattr("orchestrator.ai.memory.remember", lambda *_a, **_k: None)

    run_ai_mission(
        job=job,
        job_id=job_id,
        target="example.test",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=True,
        seed_plan=[
            {
                "name": "recon",
                "parallel": True,
                "tools": [{"tool": "httpx", "args": []}],
            }
        ],
    )

    assert revoked == ["child-1", "child-2"]
    assert playbook_jobs[job_id]["state"] in {"CANCEL_REQUESTED", "CANCELLED"}


def test_runner_reloads_shared_cancellation_before_scheduling(monkeypatch):
    job_id = "stale-worker-job"
    playbook_jobs[job_id] = {"state": "STARTED", "phases": []}
    worker_snapshot = {"state": "STARTED", "phases": []}
    scheduled: list[str] = []

    playbook_jobs.mutate_lifecycle(
        job_id,
        lambda job: {
            **job,
            "state": "CANCEL_REQUESTED",
            "cancel_requested": True,
        },
    )
    monkeypatch.setattr(
        "orchestrator.ai.runner.build_phase_workflow",
        lambda *_a, **_k: scheduled.append("workflow"),
    )
    monkeypatch.setattr("orchestrator.ai.memory.remember", lambda *_a, **_k: None)

    run_ai_mission(
        job=worker_snapshot,
        job_id=job_id,
        target="example.test",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        confirm_high_risk=True,
        seed_plan=[{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}],
    )

    assert scheduled == []
    assert playbook_jobs[job_id]["state"] in {"CANCEL_REQUESTED", "CANCELLED"}
