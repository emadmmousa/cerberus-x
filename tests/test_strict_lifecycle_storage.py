"""Strict shared-storage guarantees for mission lifecycle mutations."""

from __future__ import annotations

import pytest

from orchestrator.job_store import SharedLifecycleStoreUnavailable, playbook_jobs
from orchestrator.services import missions
from utils.redis_utils import _MemoryRedis


class WatchError(Exception):
    pass


class FakePipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self.redis = redis
        self.key = ""
        self.value = ""

    def watch(self, key: str) -> None:
        self.key = key

    def get(self, key: str) -> str | None:
        return self.redis.get(key)

    def unwatch(self) -> None:
        return None

    def multi(self) -> None:
        return None

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self.key, self.value = key, value

    def execute(self) -> None:
        if self.redis.inject_cancel_once:
            self.redis.inject_cancel_once = False
            self.redis.set_cancelled(self.key)
            raise WatchError()
        self.redis.set(self.key, self.value)

    def reset(self) -> None:
        return None


class FakeRedis:
    """Small WATCH/MULTI fake that can deterministically race cancellation."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.inject_cancel_once = False

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> bool:
        self.data[key] = value
        return True

    def setex(self, key: str, _ttl: int, value: str) -> bool:
        return self.set(key, value)

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    def set_cancelled(self, key: str) -> None:
        import json

        job = json.loads(self.data[key])
        job.update(state="CANCEL_REQUESTED", cancel_requested=True)
        self.data[key] = json.dumps(job)


@pytest.fixture
def shared_redis(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr("orchestrator.job_store._redis", lambda: redis)
    playbook_jobs._local.clear()
    yield redis
    playbook_jobs._local.clear()


def put_job(job_id: str = "job-1") -> None:
    playbook_jobs[job_id] = {
        "task_id": job_id,
        "state": "STARTED",
        "org_id": "default",
        "phases": [],
        "results": {},
    }


def test_strict_lifecycle_mutation_rejects_process_local_redis(monkeypatch):
    """Cancellation cannot be acknowledged from a replica-local fallback."""
    monkeypatch.setattr("orchestrator.job_store._redis", lambda: _MemoryRedis())

    with pytest.raises(SharedLifecycleStoreUnavailable):
        playbook_jobs.mutate_lifecycle("job-1", lambda job: job)


def test_create_job_record_rejects_process_local_redis(monkeypatch):
    """A launch must not succeed unless its record is shared durably."""
    monkeypatch.setattr("orchestrator.job_store._redis", lambda: _MemoryRedis())

    with __import__("orchestrator.dashboard", fromlist=["app"]).app.test_request_context():
        with pytest.raises(SharedLifecycleStoreUnavailable):
            missions.create_job_record(
                "job-1",
                target="example.test",
                use_proxy=False,
                proxy_protocol="http",
                ai_mode=False,
                nl_goal="test",
                posture="balanced",
            )

    assert "job-1" not in playbook_jobs._local


def test_create_job_record_persists_osint_seeds_with_initial_record(shared_redis):
    seeds = [{"kind": "domain", "value": "example.test"}]

    with __import__("orchestrator.dashboard", fromlist=["app"]).app.test_request_context():
        record = missions.create_job_record(
            "job-1",
            target="example.test",
            use_proxy=False,
            proxy_protocol="http",
            ai_mode=False,
            nl_goal="test",
            posture="balanced",
            osint_seeds=seeds,
        )

    assert record["osint_seeds"] == seeds
    assert playbook_jobs.reload_authoritative("job-1")["osint_seeds"] == seeds


def test_cancel_race_preserves_phase_result_evidence(shared_redis):
    put_job()
    shared_redis.inject_cancel_once = True

    updated = missions.merge_phase_result(
        "job-1", "recon", [{"tool": "dnsx", "hosts": ["example.test"]}], []
    )

    assert updated["state"] == "CANCEL_REQUESTED"
    assert updated["cancel_requested"] is True
    assert updated["results"]["recon"][0]["tool"] == "dnsx"


@pytest.mark.parametrize("state,error", [("SUCCESS", None), ("FAILURE", "boom")])
def test_cancel_race_wins_over_terminal_outcome(shared_redis, state, error):
    put_job()
    shared_redis.inject_cancel_once = True

    updated = missions.record_mission_outcome("job-1", state=state, error=error)

    assert updated["state"] == "CANCEL_REQUESTED"
    assert updated["cancel_requested"] is True
    assert updated.get("error") == error


def test_dashboard_success_write_finalizes_a_concurrent_cancellation(
    monkeypatch, shared_redis
):
    from orchestrator import dashboard

    put_job()
    original = missions.record_mission_outcome

    def cancel_then_record(job_id: str, **kwargs):
        playbook_jobs.mutate_lifecycle(
            job_id,
            lambda job: {
                **job,
                "state": "CANCEL_REQUESTED",
                "cancel_requested": True,
            },
        )
        return original(job_id, **kwargs)

    monkeypatch.setattr(missions, "record_mission_outcome", cancel_then_record)
    monkeypatch.setattr(dashboard, "init_db", lambda: None)
    monkeypatch.setattr(
        "orchestrator.celery_errors.assert_full_arsenal_ready", lambda: None
    )

    dashboard._run_playbook_job("job-1", "example.test", {"phases": []})

    assert playbook_jobs.reload_authoritative("job-1")["state"] == "CANCELLED"


def test_missing_lifecycle_record_is_a_typed_strict_failure(shared_redis):
    with pytest.raises(SharedLifecycleStoreUnavailable, match="record"):
        playbook_jobs.mutate_lifecycle("missing", lambda job: job)


def test_pipeline_creation_outage_is_a_typed_strict_failure(monkeypatch):
    class BrokenPipelineRedis:
        def pipeline(self):
            raise RuntimeError("connection dropped")

    monkeypatch.setattr(
        "orchestrator.job_store._redis", lambda: BrokenPipelineRedis()
    )

    with pytest.raises(SharedLifecycleStoreUnavailable):
        playbook_jobs.mutate_lifecycle("job-1", lambda job: job)


def test_runner_does_not_schedule_when_authoritative_record_is_missing(
    monkeypatch, shared_redis
):
    from orchestrator.ai.runner import run_ai_mission

    scheduled: list[str] = []
    monkeypatch.setattr(
        "orchestrator.ai.runner.build_phase_workflow",
        lambda *_args, **_kwargs: scheduled.append("scheduled"),
    )

    with pytest.raises(SharedLifecycleStoreUnavailable):
        run_ai_mission(
            job={},
            job_id="missing",
            target="example.test",
            use_proxy=False,
            proxy_protocol="http",
            evasion={},
            seed_plan=[{"name": "recon", "tools": [{"tool": "httpx", "args": []}]}],
        )

    assert scheduled == []


def test_dashboard_skipped_phase_retains_evidence_during_cancel_race(
    monkeypatch, shared_redis
):
    from orchestrator import dashboard

    put_job()
    original_append = missions.append_phase_evidence

    def cancel_then_append(job_id, phase_record):
        shared_redis.inject_cancel_once = True
        return original_append(job_id, phase_record)

    monkeypatch.setattr(missions, "append_phase_evidence", cancel_then_append)
    monkeypatch.setattr(dashboard, "init_db", lambda: None)
    monkeypatch.setattr(
        "orchestrator.celery_errors.assert_full_arsenal_ready", lambda: None
    )

    dashboard._run_playbook_job(
        "job-1",
        "example.test",
        {"phases": [{"name": "recon", "tools": [], "when": "false"}]},
    )

    job = playbook_jobs.reload_authoritative("job-1")
    assert job["state"] == "CANCELLED"
    assert job["phases"] == [
        {"phase": "recon", "error": "skipped: condition not met: false"}
    ]


def test_restarted_ai_cancellation_wins_over_success(monkeypatch, shared_redis):
    import threading

    put_job("source")
    source = playbook_jobs["source"]
    source.update(target="example.test", ai_mode=True, use_proxy=False, posture="balanced")
    playbook_jobs["source"] = source
    targets = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            del daemon
            targets.append(target)

        def start(self):
            return None

    def cancel_during_run(*, job_id, **_kwargs):
        playbook_jobs.mutate_lifecycle(
            job_id,
            lambda job: {
                **job,
                "state": "CANCEL_REQUESTED",
                "cancel_requested": True,
            },
        )

    monkeypatch.setattr(threading, "Thread", FakeThread)
    monkeypatch.setattr("uuid.uuid4", lambda: "restart")
    monkeypatch.setattr("orchestrator.ai.runner.run_ai_mission", cancel_during_run)

    from orchestrator import dashboard

    with dashboard.app.test_request_context():
        from flask import session

        session.update(user="alice", role="operator", org_id="default")
        restarted = missions.restart_mission("source")
    targets[0]()

    assert restarted["task_id"] == "restart"
    assert playbook_jobs.reload_authoritative("restart")["state"] == "CANCELLED"


def test_stop_uses_authoritative_snapshot_for_phase_revocation(monkeypatch, shared_redis):
    put_job()
    shared_redis.set(
        playbook_jobs._rkey("job-1"),
        __import__("json").dumps(
            {
                "task_id": "job-1",
                "state": "STARTED",
                "org_id": "default",
                "phases": [{"task_id": "new-phase"}],
            }
        ),
    )
    playbook_jobs._local["job-1"]["phases"] = [{"task_id": "stale-phase"}]
    revoked: list[str] = []
    monkeypatch.setattr(
        "celery.result.AsyncResult.revoke",
        lambda self, **_kwargs: revoked.append(self.id),
    )

    with __import__("orchestrator.dashboard", fromlist=["app"]).app.test_request_context():
        from flask import session

        session.update(user="alice", role="operator", org_id="default")
        result = missions.stop_mission("job-1")

    assert result["state"] == "STOPPED"
    assert revoked == ["job-1", "new-phase"]
    assert playbook_jobs.reload_authoritative("job-1")["state"] == "STOPPED"


def test_retry_links_new_job_with_atomic_mutation(monkeypatch, shared_redis):
    put_job("source")
    source = playbook_jobs.reload_authoritative("source")
    source["state"] = "FAILURE"
    shared_redis.set(playbook_jobs._rkey("source"), __import__("json").dumps(source))
    playbook_jobs._local["source"] = dict(source)

    def fake_restart(_job_id, *, source_job=None):
        assert source_job["task_id"] == "source"
        missions.create_job_record(
            "retry",
            target="example.test",
            use_proxy=False,
            proxy_protocol="http",
            ai_mode=False,
            nl_goal="test",
            posture="balanced",
        )
        return {"task_id": "retry", "restarted_from": "source", "state": "PENDING"}

    monkeypatch.setattr(missions, "restart_mission", fake_restart)
    with __import__("orchestrator.dashboard", fromlist=["app"]).app.test_request_context():
        from flask import session

        session.update(user="alice", role="operator", org_id="default")
        result = missions.retry_mission("source")

    assert result["task_id"] == "retry"
    assert playbook_jobs.reload_authoritative("retry")["retried_from"] == "source"
