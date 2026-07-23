"""Mission chat agent HTTP API."""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any

import yaml
from flask import Blueprint, Response, jsonify, request, stream_with_context

from orchestrator.ai.posture import DEFAULT_POSTURE, normalize_posture
from orchestrator.chat import intake, store as chat_store
from orchestrator.chat.targets import is_web_engagement_target, normalize_engagement_target
from orchestrator.playbook_catalog import playbook_for_posture
from orchestrator.services import missions as mission_svc
from security.audit import audit_log
from security.rbac import Role, require_role, tenant_id
from tools.proxy_config import ALLOWED_PROTOCOLS

chat_missions_bp = Blueprint("chat_missions_api", __name__)


@chat_missions_bp.get("/api/chat/config")
@require_role(Role.VIEWER)
def chat_agent_config():
    from orchestrator.ai.llm import chat_model, llm_configured, llm_reachable
    from orchestrator.chat.options import list_chat_models
    from orchestrator.osint.breach_branding import sanitize_provider_status
    from orchestrator.osint.breach_providers import provider_status

    configured = llm_configured()
    return jsonify(
        {
            "llm_configured": configured,
            "llm_reachable": llm_reachable() if configured else False,
            "models": list_chat_models(),
            "default_model": chat_model(),
            "postures": [
                {"id": "aggressive", "label": "Aggressive", "power": 3},
                {"id": "balanced", "label": "Balanced", "power": 2},
                {"id": "defensive", "label": "Defensive", "power": 1},
            ],
            "features": {
                "deep_think": True,
                "web_search": True,
                "attachments": True,
                "model_switcher": True,
                "power_switcher": True,
                "cerberus_x": True,
            },
            "defaults": {
                "deep_think": True,
                "web_search": False,
                "posture": "aggressive",
                "model": chat_model(),
            },
            "attachment_limits": {
                "max_files": 3,
                "max_bytes": 96000,
            },
            "breach_intel": sanitize_provider_status(provider_status()),
        }
    )


@chat_missions_bp.get("/api/chat/prompts")
@require_role(Role.VIEWER)
def chat_prompts_catalog():
    from orchestrator.chat.prompts_catalog import list_chat_prompts

    posture = request.args.get("posture")
    rows = list_chat_prompts(posture=posture)
    return jsonify(
        {
            "count": len(rows),
            "posture": posture or "aggressive",
            "prompts": rows,
            "note": "Full Strike Library UI ships 20 curated prompts in the frontend catalog.",
        }
    )


def _stealth_to_evasion(stealth: str | None) -> str:
    if stealth == "off":
        return "off"
    if stealth == "low":
        return "low"
    return "aggressive"


def _start_mission(
    *,
    target: str,
    posture: str = DEFAULT_POSTURE,
    nl_goal: str = "",
    stealth: str | None = "high",
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    confirm_high_risk: bool = True,
    ai_mode: bool = True,
    seed_plan: list | None = None,
    until_vulns: bool = False,
    adaptive_attack: bool = False,
    osint_seeds: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Start a mission using the same path as POST /api/run."""
    from orchestrator import dashboard as dash

    target = (target or "").strip()
    if not target:
        raise ValueError("target is required")
    if proxy_protocol not in ALLOWED_PROTOCOLS:
        raise ValueError("invalid proxy_protocol")

    # Authorization gate: when FIREBREAK_REQUIRE_AUTHZ is on, only launch against
    # hosts on the authorized-target list. No-op (allow) when enforcement is off.
    from scanner import enforce_launch_authorization

    seeds = enforce_launch_authorization(
        target, osint_seeds=osint_seeds, posture=posture, path="chat"
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
        osint_seeds=seeds,
    )

    if posture == "defensive":
        confirm_high_risk = False

    if ai_mode:
        from orchestrator.ai.runner import run_ai_mission

        def _ai_job():
            job = mission_svc.mark_mission_started(job_id)
            if job is None:
                raise RuntimeError("mission state unavailable")
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
                    until_vulns=until_vulns,
                    adaptive_attack=adaptive_attack,
                    osint_seeds=seeds,
                    add_log=dash.add_log,
                )
                if mission_svc.cancellation_requested(job_id):
                    job = mission_svc.finalize_cancellation(job_id)
                else:
                    job = mission_svc.record_mission_outcome(job_id, state="SUCCESS")
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


def _resolve_launch_plan(thread: dict, body: dict, draft: dict) -> tuple[dict | None, str, str, str, Any, str]:
    target = str(body.get("target") or draft.get("target") or "").strip()
    explicit_posture = body.get("posture") or draft.get("posture")
    posture = normalize_posture(str(explicit_posture or DEFAULT_POSTURE))
    nl_goal = str(body.get("nl_goal") or draft.get("nl_goal") or "").strip()
    stealth = body.get("stealth", draft.get("stealth"))
    if stealth in ("", "null"):
        stealth = None

    plan = draft.get("plan") if isinstance(draft.get("plan"), dict) else None
    if not plan and isinstance(body.get("plan"), dict):
        plan = body["plan"]
    if not plan:
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in thread.get("messages") or []
            if m.get("role") in ("user", "assistant")
        ]
        found = intake.find_execution_plan(history) or intake.compile_plan_from_chat(history)
        if found:
            plan = found
            if not nl_goal and found.get("nl_goal"):
                nl_goal = found["nl_goal"]
            if not target and found.get("target"):
                target = found["target"]
            if found.get("posture") and not explicit_posture:
                posture = normalize_posture(str(found["posture"]))

    if plan:
        if not target:
            target = str(plan.get("target") or draft.get("target") or "")
        plan = intake.finalize_execution_plan({**plan, "target": target})
        target = str(plan.get("target") or target)
        if plan.get("nl_goal") and not nl_goal:
            nl_goal = str(plan.get("nl_goal") or "")
        if plan.get("posture") and not explicit_posture:
            posture = normalize_posture(str(plan.get("posture") or posture))

    from orchestrator.osint.seeds import OSINT_TOOLS, normalize_osint_seeds, primary_osint_mission_target

    osint_seeds = normalize_osint_seeds(draft.get("osint_seeds") or body.get("osint_seeds"))
    tool_names = (plan or {}).get("tool_names") or []
    is_osint = bool(osint_seeds) and (
        bool((plan or {}).get("osint_only"))
        or (tool_names and all(str(tool).lower() in OSINT_TOOLS for tool in tool_names))
    )
    if is_osint and osint_seeds:
        target = primary_osint_mission_target(osint_seeds)
    elif osint_seeds and not target:
        target = primary_osint_mission_target(osint_seeds)
    if is_web_engagement_target(target):
        ctx = normalize_engagement_target(target)
        if ctx and ctx.get("host"):
            target = str(ctx.get("host") or target)
    else:
        ctx = {}

    return plan, target, posture, nl_goal, stealth, ctx


def _enrich_chat_seeds(
    agent_opts: Any,
    content: str,
    history: list[dict[str, str]],
) -> None:
    from orchestrator.osint.seeds import resolve_osint_seeds_for_chat

    agent_opts.osint_seeds = resolve_osint_seeds_for_chat(
        agent_opts.osint_seeds,
        content,
        messages=history,
    )


def _apply_osint_to_proposal(
    proposal: dict[str, Any],
    agent_opts: Any,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    from orchestrator.osint.seeds import apply_osint_seeds_to_proposal

    user_text = ""
    for msg in reversed(history):
        if msg.get("role") == "user":
            user_text = str(msg.get("content") or "")
            break
    osint_only = intake.wants_osint_only(user_text, history)
    return apply_osint_seeds_to_proposal(
        proposal,
        agent_opts.osint_seeds,
        osint_only=osint_only,
    )


def _merge_tool_proposal_into_plan(
    plan: dict | None,
    tool_proposal: dict | None,
) -> dict | None:
    if not plan or not tool_proposal:
        return plan
    from orchestrator.tools_registry import ensure_plan_new_tools

    merged = dict(plan)
    entries = list(merged.get("new_tools") or [])
    name = str(tool_proposal.get("name") or "").strip().lower()
    if name and not any(
        str(item.get("name") or "").strip().lower() == name
        for item in entries
        if isinstance(item, dict)
    ):
        entries.append(tool_proposal)
    merged["new_tools"] = entries
    return ensure_plan_new_tools(merged)


def _register_plan_tools(
    plan: dict,
    *,
    created_by: str | None,
    org_id: str | None,
    chat_id: str,
) -> list[str]:
    from orchestrator.tools_registry import get_tool, register_plan_tools

    registered = register_plan_tools(
        plan,
        created_by=created_by,
        org_id=org_id,
    )
    for name in registered:
        row = get_tool(name) or {"name": name}
        audit_log(
            "CUSTOM_TOOL_REGISTERED",
            {
                "name": name,
                "binary": row.get("binary"),
                "via": "chat_launch",
                "chat_id": chat_id,
            },
        )
    return registered


def _execute_chat_mission(
    chat_id: str,
    thread: dict,
    body: dict,
    *,
    draft: dict | None = None,
    tool_proposal: dict | None = None,
) -> dict[str, Any]:
    from flask import session

    draft = draft or thread.get("draft") or {}
    plan, target, posture, nl_goal, stealth, _ctx = _resolve_launch_plan(thread, body, draft)
    from orchestrator.osint.seeds import normalize_osint_seeds

    osint_seeds = normalize_osint_seeds(draft.get("osint_seeds") or body.get("osint_seeds"))
    if plan and tool_proposal:
        plan = _merge_tool_proposal_into_plan(plan, tool_proposal)
    confirm_high_risk = bool(body.get("confirm_high_risk", True))

    if not target or not (
        draft.get("ready") or body.get("target") or (plan and plan.get("phases"))
    ):
        raise ValueError("no ready proposal to launch")

    from orchestrator.celery_errors import assert_full_arsenal_ready

    assert_full_arsenal_ready()

    registered_tools = _register_plan_tools(
        plan or {},
        created_by=session.get("user") or session.get("auth_method"),
        org_id=session.get("org_id") or thread.get("org_id"),
        chat_id=chat_id,
    )
    seed_plan = list((plan or {}).get("phases") or [])
    until_vulns = bool(
        body.get("until_vulns")
        or draft.get("until_vulns")
        or (plan or {}).get("until_vulns")
    )
    adaptive_attack = bool(
        body.get("adaptive_attack")
        or draft.get("adaptive_attack")
        or (plan or {}).get("adaptive_attack")
        or until_vulns
    )

    from tools.proxy_policy import parse_launch_use_proxy

    resolved_evasion = _stealth_to_evasion(stealth if stealth is not None else "high")
    use_proxy = parse_launch_use_proxy(body, evasion=resolved_evasion)

    result = _start_mission(
        target=target,
        posture=posture,
        nl_goal=nl_goal,
        stealth=stealth if stealth is not None else "high",
        use_proxy=use_proxy,
        proxy_protocol=str(body.get("proxy_protocol") or "http"),
        confirm_high_risk=confirm_high_risk,
        ai_mode=bool(body.get("ai_mode", True)),
        seed_plan=seed_plan or None,
        until_vulns=until_vulns,
        adaptive_attack=adaptive_attack,
        osint_seeds=osint_seeds,
    )

    task_id = result["task_id"]
    thread.setdefault("mission_ids", []).append(task_id)
    chat_store.clear_draft(thread)
    tools_note = ""
    if until_vulns or adaptive_attack:
        tools_note = " — adaptive attack (study → rotate → invent)"
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
            "auto_execute": bool(body.get("auto_execute")),
        },
        severity="high",
    )
    return {
        **result,
        "chat_id": chat_id,
        "registered_tools": registered_tools,
        "messages": (chat_store.get_chat(chat_id) or thread).get("messages"),
    }


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
    from utils.text_encoding import ensure_utf8_text

    content = ensure_utf8_text(str(body.get("content") or "").strip())
    if not content:
        return jsonify({"error": "content is required"}), 400

    from orchestrator.chat.options import parse_chat_options

    agent_opts = parse_chat_options(body)
    chat_store.append_message(
        thread,
        "user",
        content,
        attachments=[a.as_dict() for a in agent_opts.attachments] or None,
        agent_options=agent_opts.as_dict(),
    )
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in thread.get("messages") or []
        if m.get("role") in ("user", "assistant")
    ]
    panel_seeds = list(agent_opts.osint_seeds)

    cerberus_reply = intake.try_cerberus_command(content, history)
    if cerberus_reply is not None:
        proposal = intake.detect_proposal(
            history,
            assistant_reply=cerberus_reply,
            default_posture=agent_opts.normalized_posture(),
            osint_seeds=agent_opts.osint_seeds,
            auto_run=agent_opts.auto_run,
            always_run=agent_opts.always_run,
        )
        reply = intake.sync_reply_for_proposal(
            cerberus_reply,
            proposal,
            user_text=content,
            messages=history,
        )
        proposal = _apply_osint_to_proposal(proposal, agent_opts, history)
        chat_store.append_message(
            thread,
            "assistant",
            reply,
            proposal=proposal if proposal.get("ready") else None,
            thinking_content=cerberus_reply,
        )
        thread = chat_store.get_chat(chat_id) or thread
        return jsonify(
            {
                "reply": reply,
                "proposal": proposal if proposal.get("ready") else None,
                "draft": thread.get("draft"),
                "messages": thread.get("messages"),
            }
        )

    if intake.wants_authorize_targets(content):
        reply, _added = intake.authorize_chat_targets(
            draft=thread.get("draft"),
            messages=history,
            panel_seeds=panel_seeds,
        )
        from orchestrator.osint.seeds import message_scopes_osint_seeds, resolve_osint_seeds_for_chat

        for msg in reversed(history):
            if msg.get("role") != "user" or intake.wants_authorize_targets(str(msg.get("content") or "")):
                continue
            if message_scopes_osint_seeds(str(msg.get("content") or "")):
                agent_opts.osint_seeds = resolve_osint_seeds_for_chat(
                    panel_seeds,
                    str(msg.get("content") or ""),
                )
                break
        proposal = _apply_osint_to_proposal({}, agent_opts, history)
        chat_store.append_message(
            thread,
            "assistant",
            reply,
            proposal=proposal,
            thinking_content=reply,
        )
        thread = chat_store.get_chat(chat_id) or thread
        return jsonify(
            {
                "reply": reply,
                "proposal": proposal,
                "draft": thread.get("draft"),
                "messages": thread.get("messages"),
            }
        )

    _enrich_chat_seeds(agent_opts, content, history)

    failures = int(thread.get("parse_failures") or 0)
    result = intake.run_intake(history, parse_failures=failures, osint_seeds=agent_opts.osint_seeds)
    # Re-evaluate the intake result through the same deterministic proposal
    # compiler used by SSE. This applies Auto Run / Always Run consistently and
    # attaches a concrete executable plan even when the intake model only
    # returned target/posture fields.
    detected = intake.detect_proposal(
        history,
        assistant_reply=result.get("reply"),
        default_posture=agent_opts.normalized_posture(),
        osint_seeds=agent_opts.osint_seeds,
        auto_run=agent_opts.auto_run,
        always_run=agent_opts.always_run,
    )
    proposal = detected if detected.get("ready") else result["proposal"]
    proposal["posture"] = agent_opts.normalized_posture()
    proposal = _apply_osint_to_proposal(proposal, agent_opts, history)
    reply = intake.sync_reply_for_proposal(result["reply"], proposal, user_text=content, messages=history)

    # Track parse failures when not ready and no target extracted.
    if not proposal.get("ready") and not proposal.get("target"):
        thread["parse_failures"] = failures + 1
    else:
        thread["parse_failures"] = 0

    chat_store.append_message(
        thread,
        "assistant",
        reply,
        proposal=proposal,
        thinking_content=result.get("reply") or reply,
    )
    if proposal.get("ready"):
        chat_store.set_draft(thread, proposal)
        audit_log(
            "CHAT_MISSION_PROPOSE",
            {"chat_id": chat_id, "target": proposal.get("target"), "posture": proposal.get("posture")},
        )
    else:
        chat_store.set_draft(thread, proposal if proposal.get("target") else None)

    thread = chat_store.get_chat(chat_id) or thread
    mission_launched = None
    launch_error = None
    if proposal.get("auto_execute") and proposal.get("ready"):
        try:
            mission_launched = _execute_chat_mission(
                chat_id,
                thread,
                {**body, "auto_execute": True},
                draft=proposal,
            )
            thread = chat_store.get_chat(chat_id) or thread
        except (PermissionError, ValueError) as exc:
            launch_error = str(exc)
        except Exception as exc:  # keep fallback response aligned with SSE
            launch_error = str(exc)

    return jsonify(
        {
            "reply": reply,
            "proposal": proposal,
            "draft": thread.get("draft"),
            "messages": thread.get("messages"),
            "mission_launched": mission_launched,
            "launch_error": launch_error,
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
    from utils.text_encoding import ensure_utf8_text

    content = ensure_utf8_text(str(body.get("content") or "").strip())
    if not content:
        return jsonify({"error": "content is required"}), 400

    from orchestrator.chat.options import parse_chat_options

    agent_opts = parse_chat_options(body)
    chat_store.append_message(
        thread,
        "user",
        content,
        attachments=[a.as_dict() for a in agent_opts.attachments] or None,
        agent_options=agent_opts.as_dict(),
    )
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in thread.get("messages") or []
        if m.get("role") in ("user", "assistant")
    ]
    panel_seeds = list(agent_opts.osint_seeds)

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @stream_with_context
    def generate():
        cerberus_reply = intake.try_cerberus_command(content, history)
        if cerberus_reply is not None:
            proposal = intake.detect_proposal(
                history,
                assistant_reply=cerberus_reply,
                default_posture=agent_opts.normalized_posture(),
                osint_seeds=agent_opts.osint_seeds,
                auto_run=agent_opts.auto_run,
                always_run=agent_opts.always_run,
            )
            reply = intake.sync_reply_for_proposal(
                cerberus_reply,
                proposal,
                user_text=content,
                messages=history,
            )
            proposal = _apply_osint_to_proposal(proposal, agent_opts, history)
            fresh = chat_store.get_chat(chat_id) or thread
            chat_store.append_message(
                fresh,
                "assistant",
                reply,
                proposal=proposal if proposal.get("ready") else None,
                thinking_content=cerberus_reply,
            )
            fresh = chat_store.get_chat(chat_id) or fresh
            yield _sse(
                {
                    "done": True,
                    "reply": reply,
                    "proposal": proposal if proposal.get("ready") else None,
                    "tool_proposal": None,
                    "draft": fresh.get("draft"),
                    "messages": fresh.get("messages"),
                    "mission_launched": None,
                    "launch_error": None,
                }
            )
            return

        if intake.wants_authorize_targets(content):
            reply, _added = intake.authorize_chat_targets(
                draft=thread.get("draft"),
                messages=history,
                panel_seeds=panel_seeds,
            )
            from orchestrator.osint.seeds import message_scopes_osint_seeds, resolve_osint_seeds_for_chat

            for msg in reversed(history):
                if msg.get("role") != "user" or intake.wants_authorize_targets(
                    str(msg.get("content") or "")
                ):
                    continue
                if message_scopes_osint_seeds(str(msg.get("content") or "")):
                    agent_opts.osint_seeds = resolve_osint_seeds_for_chat(
                        panel_seeds,
                        str(msg.get("content") or ""),
                    )
                    break
            proposal = _apply_osint_to_proposal({}, agent_opts, history)
            fresh = chat_store.get_chat(chat_id) or thread
            chat_store.append_message(
                fresh,
                "assistant",
                reply,
                proposal=proposal,
                thinking_content=reply,
            )
            fresh = chat_store.get_chat(chat_id) or fresh
            yield _sse(
                {
                    "done": True,
                    "reply": reply,
                    "proposal": proposal,
                    "tool_proposal": None,
                    "draft": fresh.get("draft"),
                    "messages": fresh.get("messages"),
                    "mission_launched": None,
                    "launch_error": None,
                }
            )
            return

        _enrich_chat_seeds(agent_opts, content, history)

        chunks: list[str] = []
        try:
            for piece in intake.advisor_stream(history, options=agent_opts):
                chunks.append(piece)
                yield _sse({"delta": piece})
        except Exception as exc:  # pragma: no cover - network dependent
            yield _sse({"error": str(exc)})

        raw_reply = ("".join(chunks)).strip() or intake.SOFT_FALLBACK
        proposal = intake.detect_proposal(
            history,
            assistant_reply=raw_reply,
            default_posture=agent_opts.normalized_posture(),
            osint_seeds=agent_opts.osint_seeds,
            auto_run=agent_opts.auto_run,
            always_run=agent_opts.always_run,
        )
        reply = intake.sanitize_advisor_display(raw_reply)
        proposal = _apply_osint_to_proposal(proposal, agent_opts, history)
        reply = intake.sync_reply_for_proposal(reply, proposal, user_text=content, messages=history)
        tool_proposal = intake.extract_tool_proposal(reply)
        # Prefer a plan-embedded new tool if no standalone firebreak-tool block.
        if not tool_proposal and isinstance(proposal.get("plan"), dict):
            pending = proposal["plan"].get("new_tools") or []
            if pending:
                tool_proposal = pending[0]
        fresh = chat_store.get_chat(chat_id) or thread
        chat_store.append_message(
            fresh,
            "assistant",
            reply,
            proposal=proposal,
            thinking_content=raw_reply.strip() if raw_reply else "",
        )
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

        mission_launched = None
        launch_error = None
        launch_plan = proposal.get("plan") if isinstance(proposal.get("plan"), dict) else None
        if tool_proposal and launch_plan:
            launch_plan = _merge_tool_proposal_into_plan(launch_plan, tool_proposal)
            proposal = dict(proposal)
            proposal["plan"] = launch_plan
        if proposal.get("auto_execute") and proposal.get("ready"):
            try:
                mission_launched = _execute_chat_mission(
                    chat_id,
                    fresh,
                    {**body, "auto_execute": True},
                    draft=proposal,
                    tool_proposal=tool_proposal,
                )
                fresh = chat_store.get_chat(chat_id) or fresh
            except PermissionError as exc:
                launch_error = str(exc)
            except ValueError as exc:
                launch_error = str(exc)
            except Exception as exc:
                launch_error = str(exc)

        yield _sse(
            {
                "done": True,
                "reply": reply,
                "proposal": proposal,
                "tool_proposal": tool_proposal,
                "draft": fresh.get("draft"),
                "messages": fresh.get("messages"),
                "mission_launched": mission_launched,
                "launch_error": launch_error,
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
    try:
        payload = _execute_chat_mission(chat_id, thread, body)
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
    return jsonify(payload)
