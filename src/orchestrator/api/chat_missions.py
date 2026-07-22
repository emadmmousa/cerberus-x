"""Mission chat agent HTTP API."""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any

import yaml
from flask import Blueprint, Response, jsonify, request, stream_with_context

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
    seed_plan: list | None = None,
) -> dict[str, Any]:
    """Start a mission using the same path as POST /api/run."""
    from orchestrator import dashboard as dash
    from orchestrator.ai.posture import normalize_posture

    target = (target or "").strip()
    if not target:
        raise ValueError("target is required")
    if proxy_protocol not in ALLOWED_PROTOCOLS:
        raise ValueError("invalid proxy_protocol")

    # Authorization gate: when FIREBREAK_REQUIRE_AUTHZ is on, only launch against
    # hosts on the authorized-target list. No-op (allow) when enforcement is off.
    from scanner import AuthorizationEnforcer

    if not AuthorizationEnforcer.check(target):
        audit_log(
            "MISSION_AUTHZ_DENIED",
            {"target": target, "posture": posture},
            severity="high",
        )
        raise PermissionError(
            f"'{target}' is not on the authorized-target list. Add it under "
            "Admin → Targets (or authorized_targets.json) before launching."
        )

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
            seeded = bool(seed_plan)
            dash.add_log(
                f"AI mission started for {target} "
                f"(goal={nl_goal or 'default'} posture={posture}"
                f"{' seeded=' + str(len(seed_plan or [])) + ' phases' if seeded else ''})"
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
                    seed_plan=seed_plan,
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
            "seeded": bool(seed_plan),
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


@chat_missions_bp.post("/api/chat/missions/<chat_id>/stream")
@require_role(Role.OPERATOR)
def stream_message(chat_id: str):
    """Stream the advisor reply token-by-token (SSE), then finalize the thread."""
    thread, err = _load_owned(chat_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    content = str(body.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    chat_store.append_message(thread, "user", content)
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in thread.get("messages") or []
        if m.get("role") in ("user", "assistant")
    ]

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    @stream_with_context
    def generate():
        chunks: list[str] = []
        try:
            for piece in intake.advisor_stream(history):
                chunks.append(piece)
                yield _sse({"delta": piece})
        except Exception as exc:  # pragma: no cover - network dependent
            yield _sse({"error": str(exc)})

        reply = ("".join(chunks)).strip() or intake.SOFT_FALLBACK
        proposal = intake.detect_proposal(history, assistant_reply=reply)
        tool_proposal = intake.extract_tool_proposal(reply)
        # Prefer a plan-embedded new tool if no standalone firebreak-tool block.
        if not tool_proposal and isinstance(proposal.get("plan"), dict):
            pending = proposal["plan"].get("new_tools") or []
            if pending:
                tool_proposal = pending[0]
        fresh = chat_store.get_chat(chat_id) or thread
        chat_store.append_message(fresh, "assistant", reply, proposal=proposal)
        if proposal.get("ready"):
            chat_store.set_draft(fresh, proposal)
            audit_log(
                "CHAT_MISSION_PROPOSE",
                {"chat_id": chat_id, "target": proposal.get("target"),
                 "posture": proposal.get("posture")},
            )
        else:
            chat_store.set_draft(fresh, None)
        fresh = chat_store.get_chat(chat_id) or fresh
        if tool_proposal:
            audit_log(
                "CHAT_TOOL_PROPOSE",
                {"chat_id": chat_id, "name": tool_proposal.get("name"),
                 "binary": tool_proposal.get("binary")},
            )
        yield _sse(
            {
                "done": True,
                "reply": reply,
                "proposal": proposal,
                "tool_proposal": tool_proposal,
                "draft": fresh.get("draft"),
                "messages": fresh.get("messages"),
            }
        )

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
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

    # Resolve the plan to execute: draft plan → request plan → firebreak-plan
    # block in history → a plan compiled from the whole conversation. This makes
    # a confirmed order run real tools even when the model never emitted JSON.
    plan = draft.get("plan") if isinstance(draft.get("plan"), dict) else None
    if not plan and isinstance(body.get("plan"), dict):
        plan = body["plan"]
    if not plan:
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in thread.get("messages") or []
            if m.get("role") in ("user", "assistant")
        ]
        found = intake.find_execution_plan(history) or intake.compile_plan_from_chat(
            history
        )
        if found:
            plan = {
                "phases": found["phases"],
                "new_tools": found["new_tools"],
                "tool_names": found["tool_names"],
            }
            if not nl_goal and found.get("nl_goal"):
                nl_goal = found["nl_goal"]
            if not target and found.get("target"):
                target = found["target"]
            if found.get("posture") and posture == "balanced":
                posture = found["posture"]

    # Launch is the order gate: allow when we have a target and either the draft
    # was ready, the caller passed a target, or we resolved a concrete plan.
    if not target or not (
        draft.get("ready") or body.get("target") or (plan and plan.get("phases"))
    ):
        return jsonify({"error": "no ready proposal to launch"}), 400

    seed_plan = list((plan or {}).get("phases") or [])
    registered_tools: list[str] = []
    for raw in (plan or {}).get("new_tools") or []:
        if not isinstance(raw, dict):
            continue
        try:
            from flask import session

            from orchestrator.tools_registry import register_tool

            row = register_tool(
                raw,
                created_by=session.get("user") or session.get("auth_method"),
                org_id=session.get("org_id") or thread.get("org_id"),
            )
            registered_tools.append(row["name"])
            audit_log(
                "CUSTOM_TOOL_REGISTERED",
                {
                    "name": row["name"],
                    "binary": row["binary"],
                    "via": "chat_launch",
                    "chat_id": chat_id,
                },
            )
        except ValueError as exc:
            return jsonify({"error": f"new tool rejected: {exc}"}), 400

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
            seed_plan=seed_plan or None,
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc), "reason": "unauthorized_target"}), 403
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
    tools_note = ""
    if seed_plan:
        names = (plan or {}).get("tool_names") or [
            t.get("tool")
            for phase in seed_plan
            for t in (phase.get("tools") or [])
            if isinstance(t, dict)
        ]
        uniq = []
        for n in names:
            if n and n not in uniq:
                uniq.append(n)
        tools_note = f" — executing {len(seed_plan)} phase(s): {', '.join(uniq[:10])}"
    if registered_tools:
        tools_note += f" (registered: {', '.join(registered_tools)})"
    chat_store.append_message(
        thread,
        "assistant",
        f"Mission launched: {target}{tools_note}",
        mission_card={"task_id": task_id, "target": target, "state": result.get("state")},
    )
    audit_log(
        "CHAT_MISSION_LAUNCH",
        {
            "chat_id": chat_id,
            "task_id": task_id,
            "target": target,
            "posture": posture,
            "seeded_phases": len(seed_plan),
            "registered_tools": registered_tools,
        },
        severity="high",
    )
    thread = chat_store.get_chat(chat_id) or thread
    return jsonify({**result, "chat_id": chat_id, "messages": thread.get("messages")})
