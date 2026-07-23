"""Mission list / status / run / hardening controllers."""

from __future__ import annotations

import os
import threading
import uuid

import yaml
from celery.result import AsyncResult
from flask import Blueprint, jsonify, request

from orchestrator.celery_app import app as celery_app
from orchestrator.celery_errors import assert_full_arsenal_ready, worker_readiness
from orchestrator.job_store import playbook_jobs
from orchestrator.services import missions as mission_svc
from security.audit import audit_log
from security.rbac import (
    ForbiddenOrg,
    JobNotFound,
    Role,
    job_access_error_response,
    require_role,
    tenant_id,
)
from tools.proxy_config import ALLOWED_PROTOCOLS

missions_bp = Blueprint("missions_api", __name__)

DEFAULT_PLAYBOOK = os.environ.get(
    "PLAYBOOK_PATH", "playbooks/complete_dark_arsenal.yaml"
)


@missions_bp.get("/api/missions")
@require_role(Role.VIEWER)
def api_missions_list():
    try:
        limit = int(request.args.get("limit") or 50)
    except ValueError:
        limit = 50
    rows = mission_svc.list_missions(limit=limit)
    return jsonify({"count": len(rows), "org_id": tenant_id(), "missions": rows})


@missions_bp.get("/api/workers/readiness")
@require_role(Role.VIEWER)
def api_worker_readiness():
    return jsonify(worker_readiness())


@missions_bp.get("/api/missions/<job_id>/hardening")
@require_role(Role.VIEWER)
def api_mission_hardening(job_id: str):
    try:
        payload = mission_svc.hardening_payload(job_id)
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    fmt = (request.args.get("format") or "json").lower()
    if fmt == "markdown":
        return (
            payload["markdown"],
            200,
            {"Content-Type": "text/markdown; charset=utf-8"},
        )
    return jsonify(payload)


@missions_bp.post("/api/missions/<job_id>/cancel")
@require_role(Role.OPERATOR)
def api_mission_cancel(job_id: str):
    try:
        return jsonify(mission_svc.request_cancel(job_id))
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@missions_bp.post("/api/missions/<job_id>/retry")
@require_role(Role.OPERATOR)
def api_mission_retry(job_id: str):
    try:
        return jsonify(mission_svc.retry_mission(job_id))
    except (JobNotFound, ForbiddenOrg) as exc:
        return job_access_error_response(exc)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@missions_bp.get("/status/<task_id>")
@require_role(Role.VIEWER)
def task_status(task_id: str):
    if task_id in playbook_jobs:
        try:
            job = mission_svc.get_mission(task_id)
        except (JobNotFound, ForbiddenOrg) as exc:
            return job_access_error_response(exc)
        return jsonify(job)
    result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "state": result.state,
        "info": result.info,
    }
    if result.state == "SUCCESS":
        response["result"] = result.result
    return jsonify(response)


@missions_bp.post("/api/run")
@require_role(Role.OPERATOR)
def api_run():
    """Submit a playbook or AI-mode mission for a target."""
    from orchestrator import dashboard as dash

    body = request.get_json(silent=True) or {}
    target = request.args.get("target") or body.get("target")
    if not target:
        return jsonify({"error": "target is required"}), 400

    use_proxy = bool(body.get("use_proxy", False))
    proxy_protocol = body.get("proxy_protocol") or "http"
    if proxy_protocol not in ALLOWED_PROTOCOLS:
        return jsonify({"error": "invalid proxy_protocol"}), 400

    # Authorization gate — every launch path enforces the authorized-target
    # allowlist (no-op when FIREBREAK_REQUIRE_AUTHZ is off).
    from scanner import enforce_launch_authorization

    try:
        osint_seeds = enforce_launch_authorization(
            target,
            osint_seeds=body.get("osint_seeds"),
            posture=body.get("posture"),
            path="/api/run",
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc), "reason": "unauthorized_target"}), 403

    ai_mode = bool(body.get("ai_mode", False))
    nl_goal = str(body.get("nl_goal") or body.get("goal") or "").strip()
    confirm_high_risk = bool(body.get("confirm_high_risk", False))
    from orchestrator.ai.posture import DEFAULT_POSTURE, normalize_posture
    from orchestrator.playbook_catalog import playbook_for_posture

    posture = normalize_posture(str(body.get("posture") or DEFAULT_POSTURE))
    playbook_path = (
        request.args.get("playbook")
        or body.get("playbook")
        or playbook_for_posture(posture)
    )
    try:
        with open(playbook_path) as handle:
            playbook = yaml.safe_load(handle)
    except FileNotFoundError:
        return jsonify({"error": f"playbook not found: {playbook_path}"}), 404

    evasion_override = body.get("evasion")
    if evasion_override is not None and not isinstance(evasion_override, (str, dict)):
        return jsonify({"error": "invalid evasion"}), 400
    resolved_evasion = dash._resolve_evasion(playbook, evasion_override)

    try:
        assert_full_arsenal_ready()
    except RuntimeError as exc:
        return (
            jsonify(
                {
                    "error": str(exc),
                    "reason": "worker_preflight_failed",
                }
            ),
            503,
        )

    job_id = str(uuid.uuid4())
    mission_svc.create_job_record(
        job_id,
        target=target,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        ai_mode=ai_mode,
        nl_goal=nl_goal,
        posture=posture,
        osint_seeds=osint_seeds,
    )

    if ai_mode:
        from orchestrator.ai.runner import run_ai_mission

        def _ai_job():
            cancelled = mission_svc.authoritative_cancellation_state(job_id)
            if cancelled is None:
                dash.add_log(f"AI mission state unavailable before start for {target}", level="ERROR")
                return
            if cancelled:
                mission_svc.finalize_cancellation(job_id)
                dash.add_log(f"AI mission cancelled before start for {target}")
                audit_log("AI_MISSION_CANCELLED", {"job_id": job_id, "target": target})
                return
            job = mission_svc.mark_mission_started(job_id)
            if job is None:
                raise RuntimeError("mission state unavailable")
            dash.add_log(
                f"AI mission started for {target} "
                f"(goal={nl_goal or 'default'} posture={posture})"
            )
            try:
                from orchestrator.ai.prompts import persona_banner

                dash.add_log(persona_banner(posture))
                run_ai_mission(
                    job=job,
                    job_id=job_id,
                    target=target,
                    use_proxy=use_proxy,
                    proxy_protocol=proxy_protocol,
                    evasion=resolved_evasion,
                    nl_goal=nl_goal,
                    confirm_high_risk=confirm_high_risk,
                    posture=posture,
                    osint_seeds=osint_seeds,
                    add_log=dash.add_log,
                )
                if mission_svc.cancellation_requested(job_id):
                    job = mission_svc.finalize_cancellation(job_id)
                else:
                    job = mission_svc.record_mission_outcome(
                        job_id, state="SUCCESS"
                    )
                if job is None:
                    raise RuntimeError("mission state unavailable")
                if job.get("state") == "CANCEL_REQUESTED":
                    job = mission_svc.finalize_cancellation(job_id)
                if job.get("state") == "CANCELLED":
                    dash.add_log(f"AI mission cancelled for {target}")
                    audit_log("AI_MISSION_CANCELLED", {"job_id": job_id, "target": target})
                else:
                    dash.add_log(f"AI mission finished for {target}")
                    audit_log("AI_MISSION_COMPLETE", {"job_id": job_id, "target": target})
            except Exception as exc:
                if mission_svc.cancellation_requested(job_id):
                    job = mission_svc.finalize_cancellation(job_id)
                else:
                    job = mission_svc.record_mission_outcome(
                        job_id, state="FAILURE", error=str(exc)
                    )
                    if job is None:
                        raise RuntimeError("mission state unavailable")
                if job.get("state") == "CANCEL_REQUESTED":
                    job = mission_svc.finalize_cancellation(job_id)
                if job.get("state") == "CANCELLED":
                    dash.add_log(f"AI mission cancelled for {target}")
                    audit_log("AI_MISSION_CANCELLED", {"job_id": job_id, "target": target})
                    return
                dash.add_log(f"AI mission failed for {target}: {exc}", level="ERROR")
                audit_log(
                    "AI_MISSION_FAILED",
                    {"job_id": job_id, "target": target, "error": str(exc)},
                    severity="high",
                )

        threading.Thread(target=_ai_job, daemon=True).start()
        dash.add_log(
            f"Submitted AI job {job_id} for {target} "
            f"(proxy={use_proxy}/{proxy_protocol})"
        )
        return jsonify(
            {
                "task_id": job_id,
                "target": target,
                "state": "PENDING",
                "ai_mode": True,
            }
        )

    threading.Thread(
        target=dash._run_playbook_job,
        args=(
            job_id,
            target,
            playbook,
            use_proxy,
            proxy_protocol,
            resolved_evasion,
        ),
        daemon=True,
    ).start()
    dash.add_log(
        f"Submitted playbook job {job_id} for {target} "
        f"(proxy={use_proxy}/{proxy_protocol})"
    )
    audit_log(
        "PLAYBOOK_SUBMITTED",
        {"job_id": job_id, "target": target, "playbook": playbook_path},
    )
    return jsonify({"task_id": job_id, "target": target, "state": "PENDING"})
