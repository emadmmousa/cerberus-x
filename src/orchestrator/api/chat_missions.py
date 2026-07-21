"""Mission chat agent HTTP API."""

from __future__ import annotations

import threading
import uuid
from typing import Any

import yaml
from flask import Blueprint, jsonify, request

from orchestrator.chat import intake, store as chat_store
from orchestrator.job_store import playbook_jobs
from orchestrator.playbook_catalog import playbook_for_posture
from orchestrator.services import missions as mission_svc
from security.audit import audit_log
from security.rbac import Role, require_role, tenant_id
from tools.proxy_config import ALLOWED_PROTOCOLS

chat_missions_bp = Blueprint("chat_missions_api", __name__)


def _stealth_to_evasion(stealth: str | None) -> str:
    if stealth == "off":
        return "off"
    if stealth == "low":
        return "low"
    return "aggressive"


def _start_mission(
    *,
    target: str,
    posture: str = "balanced",
    nl_goal: str = "",
    stealth: str | None = "high",
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    confirm_high_risk: bool = True,
    ai_mode: bool = True,
) -> dict[str, Any]:
    """Start a mission using the same path as POST /api/run."""
    from orchestrator import dashboard as dash
    from orchestrator.ai.posture import normalize_posture

    target = (target or "").strip()
    if not target:
        raise ValueError("target is required")
    if proxy_protocol not in ALLOWED_PROTOCOLS:
        raise ValueError("invalid proxy_protocol")

    posture = normalize_posture(posture)
    playbook_path = playbook_for_posture(posture)
    try:
        with open(playbook_path) as handle:
            playbook = yaml.safe_load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"playbook not found: {playbook_path}") from exc

    resolved_evasion = dash._resolve_evasion(playbook, _stealth_to_evasion(stealth))
    job_id = str(uuid.uuid4())
    mission_svc.create_job_record(
        job_id,
        target=target,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        ai_mode=ai_mode,
        nl_goal=nl_goal,
        posture=posture,
    )

    if posture == "defensive":
        confirm_high_risk = False

    if ai_mode:
        from orchestrator.ai.runner import run_ai_mission

        def _ai_job():
            job = playbook_jobs[job_id]
            job["state"] = "STARTED"
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
                    add_log=dash.add_log,
                )
                job["state"] = "SUCCESS"
                playbook_jobs.persist(job_id)
                dash.add_log(f"AI mission finished for {target}")
                audit_log("AI_MISSION_COMPLETE", {"job_id": job_id, "target": target})
            except Exception as exc:
                job["state"] = "FAILURE"
                job["error"] = str(exc)
                playbook_jobs.persist(job_id)
                dash.add_log(f"AI mission failed for {target}: {exc}", level="ERROR")
                audit_log(
                    "AI_MISSION_FAILED",
                    {"job_id": job_id, "target": target, "error": str(exc)},
                    severity="high",
                )

        threading.Thread(target=_ai_job, daemon=True).start()
        return {
            "task_id": job_id,
            "target": target,
            "state": "PENDING",
            "ai_mode": True,
        }

    threading.Thread(
        target=dash._run_playbook_job,
        args=(job_id, target, playbook, use_proxy, proxy_protocol, resolved_evasion),
        daemon=True,
    ).start()
    return {"task_id": job_id, "target": target, "state": "PENDING", "ai_mode": False}


def _load_owned(chat_id: str):
    thread = chat_store.get_chat(chat_id)
    if not thread:
        return None, (jsonify({"error": "chat not found"}), 404)
    if str(thread.get("org_id") or "") != str(tenant_id()):
        return None, (jsonify({"error": "forbidden", "detail": "org mismatch"}), 403)
    return thread, None


@chat_missions_bp.post("/api/chat/missions")
@require_role(Role.OPERATOR)
def create_chat():
    chat_id = chat_store.create_chat(org_id=tenant_id())
    return jsonify({"chat_id": chat_id}), 201


@chat_missions_bp.get("/api/chat/missions/<chat_id>")
@require_role(Role.OPERATOR)
def get_chat(chat_id: str):
    thread, err = _load_owned(chat_id)
    if err:
        return err
    return jsonify(thread)


@chat_missions_bp.post("/api/chat/missions/<chat_id>/messages")
@require_role(Role.OPERATOR)
def post_message(chat_id: str):
    thread, err = _load_owned(chat_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    content = str(body.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    chat_store.append_message(thread, "user", content)
    failures = int(thread.get("parse_failures") or 0)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in thread.get("messages") or []
        if m.get("role") in ("user", "assistant")
    ]
    result = intake.run_intake(history, parse_failures=failures)
    proposal = result["proposal"]
    reply = result["reply"]

    # Track parse failures when not ready and no target extracted.
    if not proposal.get("ready") and not proposal.get("target"):
        thread["parse_failures"] = failures + 1
    else:
        thread["parse_failures"] = 0

    chat_store.append_message(thread, "assistant", reply, proposal=proposal)
    if proposal.get("ready"):
        chat_store.set_draft(thread, proposal)
        audit_log(
            "CHAT_MISSION_PROPOSE",
            {"chat_id": chat_id, "target": proposal.get("target"), "posture": proposal.get("posture")},
        )
    else:
        chat_store.set_draft(thread, proposal if proposal.get("target") else None)

    thread = chat_store.get_chat(chat_id) or thread
    return jsonify(
        {
            "reply": reply,
            "proposal": proposal,
            "draft": thread.get("draft"),
            "messages": thread.get("messages"),
        }
    )


@chat_missions_bp.post("/api/chat/missions/<chat_id>/dismiss")
@require_role(Role.OPERATOR)
def dismiss_draft(chat_id: str):
    thread, err = _load_owned(chat_id)
    if err:
        return err
    chat_store.clear_draft(thread)
    return jsonify({"ok": True, "draft": None})


@chat_missions_bp.post("/api/chat/missions/<chat_id>/launch")
@require_role(Role.OPERATOR)
def launch_chat_mission(chat_id: str):
    thread, err = _load_owned(chat_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    draft = thread.get("draft") or {}
    target = str(body.get("target") or draft.get("target") or "").strip()
    posture = str(body.get("posture") or draft.get("posture") or "balanced")
    nl_goal = str(body.get("nl_goal") or draft.get("nl_goal") or "").strip()
    stealth = body.get("stealth", draft.get("stealth"))
    if stealth in ("", "null"):
        stealth = None
    confirm_high_risk = bool(body.get("confirm_high_risk", True))

    if not target or not (draft.get("ready") or body.get("target")):
        return jsonify({"error": "no ready proposal to launch"}), 400

    try:
        result = _start_mission(
            target=target,
            posture=posture,
            nl_goal=nl_goal,
            stealth=stealth if stealth is not None else "high",
            use_proxy=bool(body.get("use_proxy", False)),
            proxy_protocol=str(body.get("proxy_protocol") or "http"),
            confirm_high_risk=confirm_high_risk,
            ai_mode=bool(body.get("ai_mode", True)),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        audit_log(
            "CHAT_MISSION_LAUNCH",
            {"chat_id": chat_id, "error": str(exc)},
            severity="high",
        )
        return jsonify({"error": str(exc)}), 500

    task_id = result["task_id"]
    thread.setdefault("mission_ids", []).append(task_id)
    chat_store.clear_draft(thread)
    chat_store.append_message(
        thread,
        "assistant",
        f"Mission launched: {target}",
        mission_card={"task_id": task_id, "target": target, "state": result.get("state")},
    )
    audit_log(
        "CHAT_MISSION_LAUNCH",
        {"chat_id": chat_id, "task_id": task_id, "target": target, "posture": posture},
        severity="high",
    )
    thread = chat_store.get_chat(chat_id) or thread
    return jsonify({**result, "chat_id": chat_id, "messages": thread.get("messages")})
