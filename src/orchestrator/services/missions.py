"""Mission / playbook job domain service."""

from __future__ import annotations

from typing import Any, Optional

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
    posture = (job.get("ai") or {}).get("posture") or job.get("posture") or "balanced"
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
    playbook_jobs[job_id] = record
    return record


def verify_job_access(job: dict[str, Any]) -> None:
    assert_job_org(job)


EDITABLE_FIELDS = ("nl_goal", "posture", "target")
_TERMINAL_STATES = {"SUCCESS", "FAILURE", "REVOKED", "STOPPED"}


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


def stop_mission(job_id: str) -> dict[str, Any]:
    """Revoke the Celery task (if any) and mark the mission stopped."""
    job = get_mission(job_id)
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
    job["state"] = "STOPPED"
    job["stopped"] = True
    playbook_jobs[job_id] = job
    playbook_jobs.persist(job_id)
    return {"task_id": job_id, "state": "STOPPED", "revoked": revoked}


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


def restart_mission(job_id: str) -> dict[str, Any]:
    """Re-dispatch a mission with its original parameters as a new job."""
    import threading
    import uuid

    from orchestrator import dashboard as dash

    job = get_mission(job_id)
    new_id = str(uuid.uuid4())
    record = create_job_record(
        new_id,
        target=job.get("target") or "",
        use_proxy=bool(job.get("use_proxy")),
        proxy_protocol=job.get("proxy_protocol") or "http",
        ai_mode=bool(job.get("ai_mode")),
        nl_goal=job.get("nl_goal") or (job.get("ai") or {}).get("goal") or "",
        posture=job.get("posture") or (job.get("ai") or {}).get("posture") or "balanced",
    )

    if record.get("ai_mode"):
        from orchestrator.ai.runner import run_ai_mission

        def _ai_job():
            j = playbook_jobs[new_id]
            j["state"] = "STARTED"
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
                j["state"] = "SUCCESS"
            except Exception as exc:
                j["state"] = "FAILURE"
                j["error"] = str(exc)
            finally:
                playbook_jobs.persist(new_id)

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
