"""Mission cancellation and retry lifecycle coverage."""

from __future__ import annotations

import pytest

from orchestrator import dashboard
from orchestrator.ai import runner
from orchestrator.api import missions as missions_api
from orchestrator.job_store import SharedLifecycleStoreUnavailable, playbook_jobs
from orchestrator.services import missions
from security.rbac import ForbiddenOrg


@pytest.fixture(autouse=True)
def clear_jobs():
    playbook_jobs._local.clear()
    yield
    playbook_jobs._local.clear()


def create_fixture_job(
    *,
    job_id: str = "mission-1",
    state: str,
    org_id: str = "org-a",
    phases: list[dict] | None = None,
) -> dict:
    job = {
        "task_id": job_id,
        "target": "example.test",
        "state": state,
        "org_id": org_id,
        "phases": phases or [],
        "use_proxy": False,
        "proxy_protocol": "http",
        "ai_mode": False,
        "nl_goal": "test mission",
        "posture": "balanced",
    }
    playbook_jobs[job_id] = job
    return job


def operator_request_context():
    ctx = dashboard.app.test_request_context()
    ctx.push()
    from flask import session

    session.update(user="alice", role="operator", org_id="org-a", auth_method="local")
    return ctx


def test_request_cancel_marks_mission_and_revokes_known_phase_tasks(monkeypatch):
    job = create_fixture_job(
        state="STARTED",
        phases=[{"phase": "recon", "task_id": "phase-1"}],
    )
    revoked: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "celery.result.AsyncResult.revoke",
        lambda self, **kwargs: revoked.append((self.id, kwargs)),
    )
    ctx = operator_request_context()
    try:
        result = missions.request_cancel(job["task_id"])
    finally:
        ctx.pop()

    assert result == {
        "task_id": job["task_id"],
        "state": "CANCEL_REQUESTED",
        "revoked_task_ids": ["phase-1"],
    }
    assert revoked == [("phase-1", {})]
    assert playbook_jobs[job["task_id"]]["cancel_requested"] is True


def test_request_cancel_fails_when_shared_write_fails(monkeypatch):
    job = create_fixture_job(state="STARTED")
    monkeypatch.setattr(
        playbook_jobs,
        "merge_shared",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("shared write failed")),
    )
    ctx = operator_request_context()
    try:
        with pytest.raises(RuntimeError, match="shared write failed"):
            missions.request_cancel(job["task_id"])
    finally:
        ctx.pop()

    assert playbook_jobs[job["task_id"]]["state"] == "STARTED"


def test_request_cancel_revokes_parallel_child_tasks_not_group_id(monkeypatch):
    job = create_fixture_job(
        state="STARTED",
        phases=[
            {
                "phase": "recon",
                "task_id": "group-1",
                "child_task_ids": ["child-1", "child-2"],
            }
        ],
    )
    revoked: list[str] = []
    monkeypatch.setattr(
        "celery.result.AsyncResult.revoke",
        lambda self, **_kwargs: revoked.append(self.id),
    )
    ctx = operator_request_context()
    try:
        result = missions.request_cancel(job["task_id"])
    finally:
        ctx.pop()

    assert result["revoked_task_ids"] == ["child-1", "child-2"]
    assert revoked == ["child-1", "child-2"]


def test_cancellation_does_not_fall_back_to_stale_local_snapshot(monkeypatch):
    playbook_jobs["stale-worker"] = {
        "task_id": "stale-worker",
        "state": "CANCEL_REQUESTED",
        "cancel_requested": True,
    }
    monkeypatch.setattr(
        playbook_jobs,
        "_shared_lifecycle_redis",
        lambda: type("MissingRedis", (), {"get": lambda _self, _key: None})(),
    )

    with pytest.raises(SharedLifecycleStoreUnavailable, match="record"):
        missions.cancellation_requested("stale-worker")


def test_post_phase_actions_do_not_enqueue_after_cancellation_race(monkeypatch):
    job: dict = {"cancel_requested": False}
    enqueued: list[str] = []

    class DecisionEngine:
        def generate_post_phase_actions(self, _phase_name, _phase_output):
            job["cancel_requested"] = True
            return [{"tool": "nuclei", "args": []}]

    monkeypatch.setattr(
        runner,
        "build_phase_workflow",
        lambda *args, **kwargs: enqueued.append(args[0]),
    )

    runner._run_post_phase_actions(
        decision_engine=DecisionEngine(),
        phase_name="recon",
        phase_output=[],
        job=job,
        job_id="mission-1",
        target="example.test",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        results_by_phase={},
        add_log=lambda _message: None,
    )

    assert enqueued == []


def test_ai_thread_does_not_start_cancelled_mission(monkeypatch, tmp_path):
    playbook_path = tmp_path / "playbook.yaml"
    playbook_path.write_text("phases: []\n")
    job_id = "cancel-before-ai-start"
    thread_targets: list[object] = []
    runner_calls: list[str] = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            del daemon
            thread_targets.append(target)

        def start(self):
            return None

    monkeypatch.setattr(missions_api.uuid, "uuid4", lambda: job_id)
    monkeypatch.setattr(missions_api.threading, "Thread", FakeThread)
    monkeypatch.setattr("orchestrator.ai.runner.run_ai_mission", lambda **_kwargs: runner_calls.append("run"))

    client = dashboard.app.test_client()
    response = client.post(
        "/api/run",
        json={
            "target": "example.test",
            "ai_mode": True,
            "playbook": str(playbook_path),
        },
    )
    assert response.status_code == 200
    cancelled = dict(playbook_jobs[job_id])
    cancelled.update(state="CANCEL_REQUESTED", cancel_requested=True)
    playbook_jobs[job_id] = cancelled

    thread_targets[0]()

    assert runner_calls == []
    assert playbook_jobs[job_id]["state"] == "CANCELLED"


def test_ai_thread_finalizes_late_cancellation(monkeypatch, tmp_path):
    playbook_path = tmp_path / "playbook.yaml"
    playbook_path.write_text("phases: []\n")
    job_id = "late-ai-cancel"
    thread_targets: list[object] = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            del daemon
            thread_targets.append(target)

        def start(self):
            return None

    def fake_run_ai_mission(*, job, **_kwargs):
        job["state"] = "CANCEL_REQUESTED"
        job["cancel_requested"] = True
        playbook_jobs[job_id] = job

    monkeypatch.setattr(missions_api.uuid, "uuid4", lambda: job_id)
    monkeypatch.setattr(missions_api.threading, "Thread", FakeThread)
    monkeypatch.setattr("orchestrator.ai.runner.run_ai_mission", fake_run_ai_mission)

    client = dashboard.app.test_client()
    response = client.post(
        "/api/run",
        json={"target": "example.test", "ai_mode": True, "playbook": str(playbook_path)},
    )
    assert response.status_code == 200
    thread_targets[0]()

    assert playbook_jobs[job_id]["state"] == "CANCELLED"


def test_retried_ai_thread_does_not_start_cancelled_mission(monkeypatch):
    source = create_fixture_job(job_id="failed-ai", state="FAILURE")
    source["ai_mode"] = True
    playbook_jobs[source["task_id"]]["ai_mode"] = True
    thread_targets: list[object] = []
    runner_calls: list[str] = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            del daemon
            thread_targets.append(target)

        def start(self):
            return None

    monkeypatch.setattr("threading.Thread", FakeThread)
    monkeypatch.setattr("uuid.uuid4", lambda: "retried-ai")
    monkeypatch.setattr(
        "orchestrator.ai.runner.run_ai_mission",
        lambda **_kwargs: runner_calls.append("run"),
    )
    ctx = operator_request_context()
    try:
        result = missions.restart_mission(source["task_id"])
    finally:
        ctx.pop()
    cancelled = dict(playbook_jobs[result["task_id"]])
    cancelled.update(
        state="CANCEL_REQUESTED",
        cancel_requested=True,
    )
    playbook_jobs[result["task_id"]] = cancelled

    thread_targets[0]()

    assert runner_calls == []
    assert playbook_jobs[result["task_id"]]["state"] == "CANCELLED"


def test_request_cancel_is_org_scoped():
    create_fixture_job(state="STARTED", org_id="org-b")
    ctx = operator_request_context()
    try:
        with pytest.raises(ForbiddenOrg, match="org"):
            missions.request_cancel("mission-1")
    finally:
        ctx.pop()


def test_retry_rejects_non_retryable_mission():
    job = create_fixture_job(state="SUCCESS")
    ctx = operator_request_context()
    try:
        with pytest.raises(ValueError, match="not retryable"):
            missions.retry_mission(job["task_id"])
    finally:
        ctx.pop()


def test_retry_creates_linked_distinct_mission(monkeypatch):
    job = create_fixture_job(state="FAILURE")

    def fake_restart(job_id: str, *, source_job: dict):
        assert source_job["task_id"] == job_id
        playbook_jobs["mission-2"] = {
            **playbook_jobs[job_id],
            "task_id": "mission-2",
            "state": "PENDING",
        }
        return {"task_id": "mission-2", "restarted_from": job_id, "state": "PENDING"}

    monkeypatch.setattr(
        missions,
        "restart_mission",
        fake_restart,
    )
    ctx = operator_request_context()
    try:
        result = missions.retry_mission(job["task_id"])
    finally:
        ctx.pop()

    assert result == {
        "task_id": "mission-2",
        "retried_from": "mission-1",
        "state": "PENDING",
    }
    assert playbook_jobs["mission-2"]["retried_from"] == "mission-1"


def test_cancel_and_retry_endpoints_require_operator_and_return_validation_errors(monkeypatch):
    create_fixture_job(state="SUCCESS")
    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "true")
    client = dashboard.app.test_client()
    with client.session_transaction() as sess:
        sess.update(user="alice", role="operator", org_id="org-a", auth_method="local")

    cancel = client.post("/api/missions/mission-1/cancel")
    retry = client.post("/api/missions/mission-1/retry")

    assert cancel.status_code == 400
    assert cancel.get_json()["error"] == "mission is not cancellable"
    assert retry.status_code == 400
    assert retry.get_json()["error"] == "mission is not retryable"
