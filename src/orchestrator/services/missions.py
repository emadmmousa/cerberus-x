"""Mission / playbook job domain service."""

from __future__ import annotations

from typing import Any, Optional

from orchestrator.ai.posture import DEFAULT_POSTURE
from orchestrator.job_store import playbook_jobs
from security.rbac import (
    ForbiddenOrg,
    JobNotFound,
    assert_job_org,
    get_job_for_tenant,
    tenant_id,
)


def list_missions(*, limit: int = 50) -> list[dict[str, Any]]:
    return playbook_jobs.list_summaries(org_id=tenant_id(), limit=limit)


def get_mission(job_id: str) -> dict[str, Any]:
    return get_job_for_tenant(job_id)


def get_mission_or_none(job_id: str) -> Optional[dict[str, Any]]:
    try:
        return get_job_for_tenant(job_id)
    except (JobNotFound, ForbiddenOrg):
        return None


def hardening_payload(job_id: str) -> dict[str, Any]:
    from orchestrator.playbook_catalog import render_hardening_markdown

    job = get_mission(job_id)
    recs = (job.get("ai") or {}).get("hardening") or job.get("hardening") or []
    posture = (job.get("ai") or {}).get("posture") or job.get("posture") or DEFAULT_POSTURE
    target = job.get("target") or ""
    return {
        "job_id": job_id,
        "target": target,
        "posture": posture,
        "recommendations": recs,
        "markdown": render_hardening_markdown(
            target, recs, posture=posture, job_id=job_id
        ),
    }


def create_job_record(
    job_id: str,
    *,
    target: str,
    use_proxy: bool,
    proxy_protocol: str,
    ai_mode: bool,
    nl_goal: str,
    posture: str,
    osint_seeds: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    org = tenant_id()
    record = {
        "task_id": job_id,
        "target": target,
        "state": "PENDING",
        "phases": [],
        "use_proxy": use_proxy,
        "proxy_protocol": proxy_protocol,
        "ai_mode": ai_mode,
        "nl_goal": nl_goal,
        "org_id": org,
        "posture": posture,
    }
    if osint_seeds:
        record["osint_seeds"] = osint_seeds
    playbook_jobs.persist_shared(job_id, record)
    return record


def verify_job_access(job: dict[str, Any]) -> None:
    assert_job_org(job)


EDITABLE_FIELDS = ("nl_goal", "posture", "target")
_TERMINAL_STATES = {"SUCCESS", "FAILURE", "REVOKED", "STOPPED"}
_CANCELLABLE_STATES = {"PENDING", "STARTED"}
RETRYABLE_STATES = {"FAILURE"}
_CANCEL_REQUESTED_STATES = {"CANCEL_REQUESTED", "CANCELLED"}


def edit_mission(job_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Patch mission metadata (nl_goal / posture / target). Org-checked."""
    job = get_mission(job_id)
    applied = {}
    for field in EDITABLE_FIELDS:
        if field in changes and changes[field] is not None:
            job[field] = changes[field]
            applied[field] = changes[field]
            if field in ("nl_goal", "posture") and isinstance(job.get("ai"), dict):
                job["ai"]["goal" if field == "nl_goal" else "posture"] = changes[field]
    playbook_jobs[job_id] = job
    playbook_jobs.persist(job_id)
    return {"task_id": job_id, "applied": applied, "state": job.get("state")}


def cancellation_requested(job_id: str) -> bool:
    """Read cancellation from the shared job record, not a worker-local copy."""
    job = playbook_jobs.reload_authoritative(job_id)
    if job is None:
        return False
    return bool(job.get("cancel_requested")) or str(job.get("state") or "").upper() in _CANCEL_REQUESTED_STATES


def authoritative_mission(job_id: str) -> dict[str, Any] | None:
    """Load the shared job record and enforce the caller's tenant boundary."""
    job = playbook_jobs.reload_authoritative(job_id)
    if job is None:
        return None
    assert_job_org(job)
    return job


def authoritative_cancellation_state(job_id: str) -> bool | None:
    """Return cancellation state; ``None`` means shared storage is unavailable."""
    job = playbook_jobs.reload_authoritative(job_id)
    if job is None:
        return None
    return bool(job.get("cancel_requested")) or str(job.get("state") or "").upper() in _CANCEL_REQUESTED_STATES


def finalize_cancellation(job_id: str) -> dict[str, Any] | None:
    """Persist terminal cancellation without overwriting collected evidence."""
    def finalize(job: dict[str, Any]) -> dict[str, Any]:
        if (
            bool(job.get("cancel_requested"))
            or str(job.get("state") or "").upper() in _CANCEL_REQUESTED_STATES
        ):
            return {**job, "state": "CANCELLED"}
        return job

    return playbook_jobs.merge_shared(job_id, finalize)


def mark_mission_started(job_id: str) -> dict[str, Any] | None:
    """Mark a job running without reviving a concurrent cancellation."""
    return playbook_jobs.mutate_lifecycle(
        job_id, lambda job: {**job, "state": "STARTED"}
    )


def record_mission_outcome(
    job_id: str, *, state: str, error: str | None = None
) -> dict[str, Any] | None:
    """Atomically record a terminal outcome while retaining cancellation state."""
    if state not in {"SUCCESS", "FAILURE"}:
        raise ValueError("invalid mission outcome")

    def merge(job: dict[str, Any]) -> dict[str, Any]:
        updated = {**job, "state": state}
        if error is not None:
            updated["error"] = error
        return updated

    return playbook_jobs.mutate_lifecycle(job_id, merge)


def revoke_task_ids(task_ids: list[str]) -> list[str]:
    """Cooperatively revoke newly dispatched task IDs without termination."""
    from celery.result import AsyncResult

    from orchestrator.celery_app import app as celery_app

    revoked: list[str] = []
    for task_id in task_ids:
        if not task_id:
            continue
        try:
            AsyncResult(task_id, app=celery_app).revoke()
        except Exception:
            continue
        revoked.append(task_id)
    return revoked


def register_phase_tasks(job_id: str, phase_record: dict[str, Any]) -> dict[str, Any] | None:
    """Append dispatched IDs to the authoritative job without losing cancellation."""
    return playbook_jobs.merge_shared(
        job_id,
        lambda job: {
            **job,
            "phases": [*(job.get("phases") or []), phase_record],
        },
    )


def append_phase_evidence(
    job_id: str, phase_record: dict[str, Any]
) -> dict[str, Any]:
    """Atomically retain non-dispatch phase evidence such as skips."""
    return playbook_jobs.mutate_lifecycle(
        job_id,
        lambda job: {
            **job,
            "phases": [*(job.get("phases") or []), phase_record],
        },
    )


def merge_phase_result(
    job_id: str, phase_name: str, phase_output: Any, failed_tools: list[str]
) -> dict[str, Any] | None:
    """Merge worker-produced evidence into a freshly reloaded shared record."""
    def merge(job: dict[str, Any]) -> dict[str, Any]:
        results = dict(job.get("results") or {})
        results[phase_name] = phase_output
        ai = dict(job.get("ai") or {})
        ai["failed_tools"] = failed_tools
        return {**job, "results": results, "ai": ai}

    return playbook_jobs.merge_shared(job_id, merge)


def merge_runner_completion(
    job_id: str, *, hardening: list[Any], finished_at: float
) -> dict[str, Any] | None:
    """Persist runner completion fields without replacing cancellation state."""
    def merge(job: dict[str, Any]) -> dict[str, Any]:
        ai = dict(job.get("ai") or {})
        ai.update({"hardening": hardening, "finished_at": finished_at})
        return {**job, "ai": ai}

    return playbook_jobs.merge_shared(job_id, merge)


def append_ai_plan(job_id: str, plan: dict[str, Any]) -> dict[str, Any] | None:
    """Append planned work without flushing a worker-local full job snapshot."""
    def merge(job: dict[str, Any]) -> dict[str, Any]:
        ai = dict(job.get("ai") or {})
        ai["steps"] = [*(ai.get("steps") or []), plan]
        return {**job, "ai": ai}

    return playbook_jobs.mutate_lifecycle(job_id, merge)


def stop_mission(job_id: str) -> dict[str, Any]:
    """Revoke the Celery task (if any) and mark the mission stopped."""
    def stop(current: dict[str, Any]) -> dict[str, Any]:
        assert_job_org(current)
        return {**current, "state": "STOPPED", "stopped": True}

    job = playbook_jobs.mutate_lifecycle(job_id, stop)
    revoked = False
    try:
        from celery.result import AsyncResult

        from orchestrator.celery_app import app as celery_app

        AsyncResult(job_id, app=celery_app).revoke(terminate=True, signal="SIGTERM")
        revoked = True
    except Exception:
        revoked = False
    for phase in job.get("phases") or []:
        pid = phase.get("task_id")
        if pid:
            try:
                from celery.result import AsyncResult
                from orchestrator.celery_app import app as celery_app

                AsyncResult(pid, app=celery_app).revoke(terminate=True, signal="SIGTERM")
            except Exception:
                pass
    return {"task_id": job_id, "state": "STOPPED", "revoked": revoked}


def request_cancel(job_id: str) -> dict[str, Any]:
    """Request cooperative cancellation without terminating active commands."""
    from celery.result import AsyncResult

    from orchestrator.celery_app import app as celery_app
    from security.audit import audit_log

    def request(current: dict[str, Any]) -> dict[str, Any]:
        assert_job_org(current)
        if str(current.get("state") or "").upper() not in _CANCELLABLE_STATES:
            raise ValueError("mission is not cancellable")
        return {**current, "cancel_requested": True, "state": "CANCEL_REQUESTED"}

    job = playbook_jobs.merge_shared(job_id, request)
    if job is None:
        raise RuntimeError("mission state unavailable")

    revoked_task_ids: list[str] = []
    for phase in job.get("phases") or []:
        child_task_ids = phase.get("child_task_ids")
        task_ids = (
            child_task_ids
            if isinstance(child_task_ids, list) and child_task_ids
            else [phase.get("task_id")]
        )
        for task_id in task_ids:
            if not task_id:
                continue
            result = AsyncResult(task_id, app=celery_app)
            # A cancellation request is cooperative: never terminate a task that
            # is already running. Only report revocations for queued phase tasks.
            if result.state != "PENDING":
                continue
            try:
                result.revoke()
            except Exception:
                continue
            revoked_task_ids.append(task_id)

    audit_log(
        "MISSION_CANCEL_REQUESTED",
        {"job_id": job_id, "revoked_task_ids": revoked_task_ids},
        severity="high",
    )
    return {
        "task_id": job_id,
        "state": "CANCEL_REQUESTED",
        "revoked_task_ids": revoked_task_ids,
    }


def delete_mission(job_id: str) -> bool:
    """Remove a mission from the store (org-checked). Stops it first if live."""
    job = get_mission(job_id)
    if str(job.get("state") or "").upper() not in _TERMINAL_STATES:
        try:
            stop_mission(job_id)
        except Exception:
            pass
    if job_id in playbook_jobs:
        del playbook_jobs[job_id]
        return True
    return False


def restart_mission(
    job_id: str, *, source_job: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Re-dispatch a mission with its original parameters as a new job."""
    import threading
    import uuid

    from orchestrator import dashboard as dash

    job = source_job or get_mission(job_id)
    verify_job_access(job)
    new_id = str(uuid.uuid4())
    record = create_job_record(
        new_id,
        target=job.get("target") or "",
        use_proxy=bool(job.get("use_proxy")),
        proxy_protocol=job.get("proxy_protocol") or "http",
        ai_mode=bool(job.get("ai_mode")),
        nl_goal=job.get("nl_goal") or (job.get("ai") or {}).get("goal") or "",
        posture=job.get("posture") or (job.get("ai") or {}).get("posture") or DEFAULT_POSTURE,
    )

    if record.get("ai_mode"):
        from orchestrator.ai.runner import run_ai_mission

        def _ai_job():
            cancelled = authoritative_cancellation_state(new_id)
            if cancelled is None:
                dash.add_log(f"Retried AI mission state unavailable before start for {record['target']}")
                return
            j = playbook_jobs[new_id]
            if cancelled:
                finalize_cancellation(new_id)
                dash.add_log(f"Retried AI mission cancelled before start for {record['target']}")
                return
            j = mark_mission_started(new_id)
            try:
                run_ai_mission(
                    job=j,
                    job_id=new_id,
                    target=record["target"],
                    use_proxy=record["use_proxy"],
                    proxy_protocol=record["proxy_protocol"],
                    evasion=None,
                    nl_goal=record["nl_goal"],
                    confirm_high_risk=False,
                    posture=record["posture"],
                    add_log=dash.add_log,
                )
                if cancellation_requested(new_id):
                    j = finalize_cancellation(new_id)
                else:
                    j = record_mission_outcome(new_id, state="SUCCESS")
                if j.get("state") == "CANCEL_REQUESTED":
                    j = finalize_cancellation(new_id)
            except Exception as exc:
                if cancellation_requested(new_id):
                    j = finalize_cancellation(new_id)
                else:
                    j = record_mission_outcome(
                        new_id, state="FAILURE", error=str(exc)
                    )
                if j.get("state") == "CANCEL_REQUESTED":
                    finalize_cancellation(new_id)

        threading.Thread(target=_ai_job, daemon=True).start()
    else:
        import yaml

        from orchestrator.playbook_catalog import playbook_for_posture

        playbook_path = playbook_for_posture(record["posture"])
        try:
            with open(playbook_path) as handle:
                playbook = yaml.safe_load(handle)
        except FileNotFoundError:
            playbook = {"phases": []}
        threading.Thread(
            target=dash._run_playbook_job,
            args=(
                new_id,
                record["target"],
                playbook,
                record["use_proxy"],
                record["proxy_protocol"],
                None,
            ),
            daemon=True,
        ).start()

    return {"task_id": new_id, "restarted_from": job_id, "state": "PENDING"}


def retry_mission(job_id: str) -> dict[str, Any]:
    """Retry a failed mission as a distinct, auditable mission."""
    from security.audit import audit_log

    def validate_retry(current: dict[str, Any]) -> dict[str, Any]:
        assert_job_org(current)
        if str(current.get("state") or "").upper() not in RETRYABLE_STATES:
            raise ValueError("mission is not retryable")
        return current

    job = playbook_jobs.mutate_lifecycle(job_id, validate_retry)
    restarted = restart_mission(job_id, source_job=job)
    new_id = restarted["task_id"]
    new_job = playbook_jobs.mutate_lifecycle(
        new_id, lambda current: {**current, "retried_from": job_id}
    )
    audit_log("MISSION_RETRIED", {"job_id": new_id, "retried_from": job_id})
    return {
        "task_id": new_id,
        "retried_from": job_id,
        "state": restarted.get("state") or new_job.get("state") or "PENDING",
    }
