"""AI mission runner (Phases 2–4)."""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Optional

from celery.exceptions import TimeoutError as CeleryTimeoutError

from orchestrator.ai import memory, planner
from orchestrator.ai.posture import DEFAULT_POSTURE
from orchestrator.cli import collect_chain_results, collect_group_results
from orchestrator.database import save_phase_result
from orchestrator.decision_engine import DecisionEngine
from orchestrator.tasks import build_phase_workflow


LogFn = Callable[[str], None]


def _phase_use_proxy(
    use_proxy: bool,
    decision_engine: DecisionEngine,
    evasion: dict,
) -> bool:
    from tools.proxy_policy import resolve_use_proxy

    state = getattr(decision_engine, "state", None) or {}
    return resolve_use_proxy(
        requested=use_proxy,
        waf_blocked=bool(state.get("waf_blocked")),
        cdn=bool(state.get("cdn")),
        evasion=evasion,
    )


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(30, int(raw))
    except ValueError:
        return default


# Per-phase wait for Celery group/chain. Keep below pathological tool hangs;
# masscan/etc. also have their own soft time limits.
PHASE_TIMEOUT_SECONDS = _env_int("FIREBREAK_PHASE_TIMEOUT", 300)
VULN_PHASE_TIMEOUT_SECONDS = _env_int("FIREBREAK_VULN_PHASE_TIMEOUT", 420)
IMPACT_PHASE_TIMEOUT_SECONDS = _env_int("FIREBREAK_IMPACT_PHASE_TIMEOUT", 480)
ACTION_TIMEOUT_SECONDS = _env_int("FIREBREAK_ACTION_TIMEOUT", 300)

_VULN_TOOLS = frozenset({"nikto", "nuclei", "ffuf", "gobuster", "xsstrike", "sqlmap"})
_HEAVY_TOOLS = frozenset({"sqlmap", "metasploit", "hydra", "nuclei", "nikto"})


def _phase_timeout_seconds(phase_name: str, tools: list[dict]) -> int:
    """Allow longer wall time for proof-of-impact / heavy exploit phases."""
    name = (phase_name or "").lower()
    tool_names = {str(t.get("tool") or "").lower() for t in tools if isinstance(t, dict)}
    if any(n.startswith("scaffold/") for n in tool_names) or "scaffold" in name:
        parallel_count = max(1, len(tool_names))
        return max(VULN_PHASE_TIMEOUT_SECONDS, 300 + parallel_count * 120)
    if "proof" in name or "impact" in name or "exploit" in name:
        return IMPACT_PHASE_TIMEOUT_SECONDS
    if tool_names & {"sqlmap", "metasploit", "hydra"} and len(tool_names) > 1:
        return IMPACT_PHASE_TIMEOUT_SECONDS
    if tool_names & _VULN_TOOLS:
        parallel_count = max(1, len(tool_names & _VULN_TOOLS))
        return max(VULN_PHASE_TIMEOUT_SECONDS, PHASE_TIMEOUT_SECONDS + (parallel_count - 1) * 90)
    if tool_names & {"sqlmap", "metasploit"}:
        return max(PHASE_TIMEOUT_SECONDS, 300)
    if tool_names & _HEAVY_TOOLS:
        return max(PHASE_TIMEOUT_SECONDS, 360)
    return PHASE_TIMEOUT_SECONDS

from tools.attack_methods import (
    aggressive_args_for,
    full_tool_rotation,
)

_HUNT_TOOL_ROTATION = full_tool_rotation()


def _partial_results(async_result) -> list[Any]:
    """Best-effort gather of finished children after a phase timeout."""
    collected: list[Any] = []
    try:
        children = getattr(async_result, "results", None) or list(async_result.children or [])
    except Exception:
        children = []
    for child in children:
        try:
            if not child.ready():
                continue
            if child.successful():
                collected.append(child.get(timeout=0))
            elif child.failed():
                collected.append(
                    {
                        "tool": "unknown",
                        "error": str(child.result) if child.result else "task failed",
                    }
                )
        except Exception:
            continue
    if not collected and async_result.successful():
        try:
            result = async_result.result
            if isinstance(result, list):
                return result
            if result is not None:
                return [result]
        except Exception:
            pass
    return collected


def _resolve_phase_name(plan: dict, step: int) -> str:
    phase_name = str(plan.get("phase_name") or f"ai_step_{step}")[:80]
    if step > 0 and not phase_name.endswith(f"_s{step}"):
        phase_name = f"{phase_name}_s{step}"[:80]
    return phase_name


def _cancel_requested(job_id: str) -> bool:
    from orchestrator.services.missions import cancellation_requested

    return cancellation_requested(job_id)


def _finalize_cancellation(job: dict[str, Any], job_id: str, log: LogFn) -> None:
    """Finish cooperatively after preserving any collected phase evidence."""
    from orchestrator.services.missions import finalize_cancellation

    authoritative = finalize_cancellation(job_id)
    if authoritative is None:
        raise RuntimeError("mission state unavailable")
    job.update(authoritative)
    if job.get("state") != "CANCELLED":
        log("Mission cancellation requested; no further phases will be scheduled.")


def _workflow_child_task_ids(async_result: Any) -> list[str]:
    """Return dispatch IDs for the individual members of a group workflow."""
    children = getattr(async_result, "results", None) or []
    return [
        child.id
        for child in children
        if isinstance(getattr(child, "id", None), str) and child.id
    ]


def _dispatched_task_ids(phase_record: dict[str, Any]) -> list[str]:
    child_task_ids = phase_record.get("child_task_ids")
    if isinstance(child_task_ids, list) and child_task_ids:
        return [task_id for task_id in child_task_ids if isinstance(task_id, str)]
    task_id = phase_record.get("task_id")
    return [task_id] if isinstance(task_id, str) else []


def _revoke_dispatched_tasks(phase_record: dict[str, Any]) -> None:
    from orchestrator.services.missions import revoke_task_ids

    revoke_task_ids(_dispatched_task_ids(phase_record))


def _record_empty_phase(
    *,
    job: dict,
    job_id: str,
    target: str,
    phase_name: str,
    reason: str,
    results_by_phase: dict[str, Any],
    decision_engine: DecisionEngine,
    log: LogFn,
) -> None:
    """Persist a skipped/empty phase so the UI does not show a silent failure."""
    log(reason)
    job.setdefault("phases", []).append({"phase": phase_name, "error": f"skipped: {reason}"})
    phase_output = [{"tool": "phase", "error": reason, "skipped": True}]
    results_by_phase[phase_name] = phase_output
    if job.get("ai", {}).get("steps"):
        job["ai"]["steps"][-1]["phase_name"] = phase_name
    save_phase_result(
        target,
        phase_name,
        phase_output,
        job_id=job_id,
        org_id=job.get("org_id"),
    )
    decision_engine.evaluate_phase(phase_name, phase_output)
    from orchestrator.services.missions import merge_phase_result

    authoritative = merge_phase_result(job_id, phase_name, phase_output, [])
    if authoritative is not None:
        job.update(authoritative)


def _hunt_max_steps() -> int:
    try:
        return max(5, int(os.getenv("FIREBREAK_HUNT_MAX_STEPS", "25")))
    except ValueError:
        return 25


def _hunt_escalation_plan(
    target: str,
    *,
    completed_tools: set[str],
    step: int,
    posture: str,
) -> dict[str, Any]:
    """Deterministic next vuln-hunt phase when the planner would otherwise stop."""
    from orchestrator.ai.posture import filter_allowlist, normalize_posture
    from orchestrator.mcp.registry import known_tools
    from tools.attack_methods import aggressive_args_for, next_hunt_strike

    allow = filter_allowlist(known_tools(), normalize_posture(posture))
    tried = set(completed_tools)
    name = next_hunt_strike(tried, allow)
    if name:
        parallel = name.startswith("scaffold/")
        args: list[str] = [] if parallel else list(aggressive_args_for(name))
        label = name.split("/")[-1] if parallel else name
        return {
            "phase_name": f"hunt_{label}_s{step}",
            "reason": f"Vuln hunt: trying {name} before stopping.",
            "parallel": parallel,
            "stop": False,
            "tools": [{"tool": name, "args": args}],
            "source": "hunt_escalation",
        }
    return {
        "phase_name": "hunt_exhausted",
        "reason": "Vuln hunt exhausted allowlisted scanners.",
        "parallel": False,
        "stop": True,
        "tools": [],
        "source": "hunt_escalation",
    }


def _max_inventions(nl_goal: str = "", *, profile: dict[str, Any] | None = None) -> int:
    try:
        base = max(1, int(os.getenv("FIREBREAK_MAX_INVENTIONS", "3")))
    except ValueError:
        base = 3
    from tools.attack_methods import wants_database_access

    if wants_database_access(nl_goal, profile=profile):
        try:
            db_cap = max(base, int(os.getenv("FIREBREAK_DB_MAX_INVENTIONS", "6")))
        except ValueError:
            db_cap = max(base, 6)
        return db_cap
    return base


_RETRY_TOOL_SOURCES = frozenset({"novel_invention", "db_access_rotation", "chat_plan"})


def _allows_tool_retry(plan: dict[str, Any]) -> bool:
    return plan.get("source") in _RETRY_TOOL_SOURCES


def _adaptive_enabled(until_vulns: bool, adaptive_attack: bool, nl_goal: str) -> bool:
    if adaptive_attack:
        return True
    if until_vulns:
        return True
    blob = (nl_goal or "").lower()
    return any(
        token in blob
        for token in (
            "until confirmed",
            "don't stop",
            "do not stop",
            "keep trying",
            "deep study",
            "full red-team",
            "find vulnerabilit",
        )
    )


def _profile_escalation_plan(
    target: str,
    *,
    profile: dict[str, Any],
    completed_tools: set[str],
    failed_tools: set[str],
    allow: set[str],
    step: int,
) -> dict[str, Any] | None:
    from orchestrator.ai.target_study import recommend_attack_tools
    from tools.attack_methods import recommend_scaffold_strikes
    from tools.normalize_args import default_args_for

    tried = completed_tools | failed_tools
    for strike in recommend_scaffold_strikes(
        profile, allow, tried=tried
    ):
        label = strike.split("/")[-1]
        return {
            "phase_name": f"scaffold_{label}_s{step}",
            "reason": f"Profile-matched scaffold strike {strike} (signals: {', '.join(profile.get('signals') or [])[:6]}).",
            "parallel": True,
            "stop": False,
            "tools": [{"tool": strike, "args": []}],
            "source": "scaffold_escalation",
        }

    for name in recommend_attack_tools(
        profile, allow, tried=tried, failed=failed_tools
    ):
        if name in tried:
            continue
        return {
            "phase_name": f"profile_{name}_s{step}",
            "reason": f"Target profile suggests {name} (signals: {', '.join(profile.get('signals') or [])[:6]}).",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": name, "args": list(default_args_for(name))}],
            "source": "profile_escalation",
        }
    return None


def _db_access_escalation_plan(
    target: str,
    nl_goal: str,
    *,
    job: dict,
    failed_tools: set[str],
    step: int,
    posture: str,
    profile: dict[str, Any],
    decision_state: dict[str, Any],
) -> dict[str, Any] | None:
    from orchestrator.ai.posture import filter_allowlist, normalize_posture
    from orchestrator.mcp.registry import known_tools
    from tools.attack_methods import next_db_access_phase, wants_database_access

    if not wants_database_access(nl_goal, profile=profile, decision_state=decision_state):
        return None

    allow = filter_allowlist(known_tools(), normalize_posture(posture))
    ai = job.setdefault("ai", {})
    tried_methods = set(ai.get("db_methods_tried") or [])
    dbms = decision_state.get("sql_dbms") or decision_state.get("dbms")
    plan = next_db_access_phase(
        allow=allow,
        tried_methods=tried_methods,
        failed_tools=failed_tools,
        dbms=str(dbms) if dbms else None,
        step=step,
    )
    if plan is None:
        return None
    method_id = plan.pop("db_method_id", None)
    if method_id:
        ai.setdefault("db_methods_tried", []).append(method_id)
    return plan


def _adaptive_escalation_plan(
    target: str,
    nl_goal: str,
    *,
    job: dict,
    completed_tools: set[str],
    failed_tools: set[str],
    step: int,
    posture: str,
    profile: dict[str, Any],
    decision_state: dict[str, Any],
    inventions_used: int,
) -> dict[str, Any]:
    """Next phase after failure or planner stop: db rotation → profile → hunt → invent."""
    from orchestrator.ai.posture import filter_allowlist, normalize_posture
    from orchestrator.mcp.registry import known_tools

    allow = filter_allowlist(known_tools(), normalize_posture(posture))

    db_plan = _db_access_escalation_plan(
        target,
        nl_goal,
        job=job,
        failed_tools=failed_tools,
        step=step,
        posture=posture,
        profile=profile,
        decision_state=decision_state,
    )
    if db_plan is not None:
        return db_plan

    profile_plan = _profile_escalation_plan(
        target,
        profile=profile,
        completed_tools=completed_tools,
        failed_tools=failed_tools,
        allow=allow,
        step=step,
    )
    if profile_plan is not None:
        return profile_plan

    hunt_plan = _hunt_escalation_plan(
        target,
        completed_tools=completed_tools | failed_tools,
        step=step,
        posture=posture,
    )
    if not hunt_plan.get("stop") and hunt_plan.get("tools"):
        return hunt_plan

    if inventions_used < _max_inventions(nl_goal, profile=profile):
        from orchestrator.ai.invention import invent_novel_attack_plan

        novel = invent_novel_attack_plan(
            target,
            nl_goal,
            profile=profile,
            failed_tools=failed_tools,
            tried_tools=completed_tools | failed_tools,
            decision_state=decision_state,
            step=step,
        )
        if novel is not None:
            return novel

    return {
        "phase_name": "adaptive_exhausted",
        "reason": "Adaptive attack exhausted profile tools, hunt rotation, and novel inventions.",
        "parallel": False,
        "stop": True,
        "tools": [],
        "source": "adaptive_escalation",
    }


def _record_phase_outcomes(
    planned_tools: list[dict[str, Any]],
    phase_output: Any,
    *,
    completed_tools: set[str],
    failed_tools: set[str],
) -> None:
    from orchestrator.ai.target_study import phase_tool_outcomes

    for name, outcome in phase_tool_outcomes(planned_tools, phase_output).items():
        if outcome == "failed":
            failed_tools.add(name)
            completed_tools.discard(name)
        else:
            completed_tools.add(name)
            failed_tools.discard(name)


def _register_plan_inventions(plan: dict[str, Any], job: dict) -> None:
    new_tools = plan.get("new_tools") or []
    if not new_tools:
        return
    from orchestrator.tools_registry import register_plan_tools

    registered = register_plan_tools(
        plan,
        created_by=job.get("created_by"),
        org_id=job.get("org_id"),
    )
    if registered:
        job.setdefault("ai", {}).setdefault("registered_tools", []).extend(registered)


def _run_post_phase_actions(
    *,
    decision_engine: DecisionEngine,
    phase_name: str,
    phase_output: Any,
    job: dict,
    job_id: str,
    target: str,
    use_proxy: bool,
    proxy_protocol: str,
    evasion: dict,
    results_by_phase: dict[str, Any],
    add_log: LogFn,
) -> None:
    """Execute DecisionEngine follow-on actions (CVE → metasploit, sqlmap aux, etc.)."""
    if _cancel_requested(job_id):
        return
    generate = getattr(decision_engine, "generate_post_phase_actions", None)
    if generate is None:
        return
    actions = generate(phase_name, phase_output)
    fired_actions: list[dict[str, Any]] = []
    for action in actions:
        if _cancel_requested(job_id):
            break
        action_name = action.get("phase") or f"auto_{action['tool']}_{phase_name}"
        add_log(f"Auto action {action_name}")
        from tools.breach_intel import inject_osint_seeds_into_tools

        action_tools = inject_osint_seeds_into_tools(
            [{"tool": action["tool"], "args": action["args"]}],
            job.get("osint_seeds"),
        )
        action_workflow = build_phase_workflow(
            action_name,
            action_tools,
            target,
            parallel=False,
            use_proxy=_phase_use_proxy(use_proxy, decision_engine, evasion),
            proxy_protocol=proxy_protocol,
            evasion=evasion,
        )
        if action_workflow is None:
            continue
        if _cancel_requested(job_id):
            break
        action_result = action_workflow.apply_async()
        action_record = {"phase": action_name, "task_id": action_result.id}
        from orchestrator.services.missions import register_phase_tasks

        authoritative = register_phase_tasks(job_id, action_record)
        if authoritative is not None:
            job.setdefault("phases", []).append(action_record)
            if authoritative.get("cancel_requested"):
                job["cancel_requested"] = True
            if authoritative.get("state") in {"CANCEL_REQUESTED", "CANCELLED"}:
                job["state"] = authoritative["state"]
        if _cancel_requested(job_id):
            _revoke_dispatched_tasks(action_record)
            _finalize_cancellation(job, job_id, add_log)
            break
        action_output = collect_chain_results(action_result, timeout=ACTION_TIMEOUT_SECONDS)
        from orchestrator.services.missions import merge_phase_result

        authoritative = merge_phase_result(job_id, action_name, action_output, [])
        if authoritative is not None:
            job.update(authoritative)
        save_phase_result(
            target,
            action_name,
            action_output,
            job_id=job_id,
            org_id=job.get("org_id"),
        )
        results_by_phase[action_name] = action_output
        decision_engine.evaluate_phase(action_name, action_output)
        fired_actions.append(action)
    mark = getattr(decision_engine, "mark_actions_fired", None)
    if mark and fired_actions:
        mark(fired_actions)


def run_ai_mission(
    *,
    job: dict,
    job_id: str,
    target: str,
    use_proxy: bool,
    proxy_protocol: str,
    evasion: dict,
    nl_goal: str = "",
    confirm_high_risk: bool = False,
    posture: str = DEFAULT_POSTURE,
    max_steps: int = 5,
    seed_plan: list[dict] | None = None,
    until_vulns: bool = False,
    adaptive_attack: bool = False,
    osint_seeds: list[dict[str, str]] | None = None,
    add_log: Optional[LogFn] = None,
) -> None:
    """
    Adaptive loop: plan → execute phase tools → evaluate → re-plan.

    When ``seed_plan`` is provided (chat-confirmed phases), those phases run
    first exactly as ordered; the LLM/heuristic planner only takes over for
    remaining adaptive steps afterward.

    High-risk tools in the plan are skipped unless confirm_high_risk is True
    (Celery enqueue path still enforces confirm for MCP; here we filter tools).
    """
    log = add_log or (lambda msg: None)
    from orchestrator.celery_errors import assert_full_arsenal_ready

    assert_full_arsenal_ready()
    from orchestrator.ai.safety import require_confirm_for_tool
    from orchestrator.ai.posture import hardening_recommendations, normalize_posture

    posture_n = normalize_posture(posture)
    from tools.proxy_policy import resolve_use_proxy

    use_proxy = resolve_use_proxy(requested=use_proxy, evasion=evasion)
    job["use_proxy"] = use_proxy
    if osint_seeds:
        job["osint_seeds"] = osint_seeds
    decision_engine = DecisionEngine(target, job_id=job_id, posture=posture_n)
    results_by_phase: dict[str, Any] = {}
    completed_tools: set[str] = set()
    failed_tools: set[str] = set()
    inventions_used = 0
    seed_phases = [
        p for p in (seed_plan or []) if isinstance(p, dict) and p.get("tools")
    ]
    if not until_vulns:
        blob = (nl_goal or "").lower()
        until_vulns = "until confirmed findings" in blob or "hunt vulnerabilities" in blob
    adaptive = _adaptive_enabled(until_vulns, adaptive_attack, nl_goal)
    hunt_cap = _hunt_max_steps()
    # Give chat-seeded missions enough steps to finish the ordered plan + follow-ups.
    if adaptive:
        from tools.attack_methods import wants_database_access

        inv_cap = _max_inventions(nl_goal)
        db_extra = 12 if wants_database_access(nl_goal) else 0
        effective_max = max(hunt_cap, len(seed_phases) + hunt_cap + inv_cap + db_extra)
    elif until_vulns:
        effective_max = max(hunt_cap, len(seed_phases) + hunt_cap)
    elif seed_phases:
        effective_max = max(max_steps, len(seed_phases) + max_steps)
    else:
        effective_max = max_steps
    job["ai"] = {
        "goal": nl_goal,
        "steps": [],
        "mode": "ai",
        "posture": posture_n,
        "seeded": bool(seed_phases),
        "seed_phases": [p.get("name") for p in seed_phases],
        "until_vulns": until_vulns,
        "adaptive_attack": adaptive,
        "failed_tools": [],
    }
    if adaptive:
        log(
            "Adaptive attack: deep study → profile-matched tools → retries → "
            f"novel inventions (max {_max_inventions(nl_goal)})"
        )
    elif until_vulns:
        log(f"Vuln hunt mode: will continue until findings or {effective_max} steps")
    if use_proxy:
        log("Proxy routing enabled (upstream residential/datacenter forwarder)")

    for step in range(effective_max):
        if _cancel_requested(job_id):
            _finalize_cancellation(job, job_id, log)
            break
        de_state = getattr(decision_engine, "state", None) or {}
        if step < len(seed_phases):
            phase = seed_phases[step]
            plan = {
                "phase_name": str(phase.get("name") or f"chat_phase_{step}")[:80],
                "reason": f"Chat-confirmed plan phase {step + 1}/{len(seed_phases)}",
                "parallel": bool(phase.get("parallel", False)),
                "stop": False,
                "tools": list(phase.get("tools") or []),
                "source": "chat_plan",
            }
        else:
            from orchestrator.ai.target_study import build_target_profile

            plan = planner.suggest_next_phase(
                target,
                results_by_phase,
                nl_goal=nl_goal,
                step=step,
                posture=posture_n,
                mission_id=job_id,
                until_vulns=until_vulns or adaptive,
                    vuln_found=bool(de_state.get("vuln_found")),
                    failed_tools=sorted(failed_tools),
                    target_profile=build_target_profile(de_state, results_by_phase),
            )
        from orchestrator.services.missions import append_ai_plan

        authoritative = append_ai_plan(job_id, plan)
        if authoritative is not None:
            job.update(authoritative)
        log(f"AI plan ({plan.get('source')}): {plan.get('reason')}")

        if plan.get("stop") or not plan.get("tools"):
            if (until_vulns or adaptive) and not de_state.get("vuln_found"):
                from orchestrator.ai.target_study import build_target_profile

                plan = _adaptive_escalation_plan(
                    target,
                    nl_goal,
                    job=job,
                    completed_tools=completed_tools,
                    failed_tools=failed_tools,
                    step=step,
                    posture=posture_n,
                    profile=build_target_profile(de_state, results_by_phase),
                    decision_state=de_state,
                    inventions_used=inventions_used,
                )
                job["ai"]["steps"].append(plan)
                log(f"AI adaptive escalation ({plan.get('source')}): {plan.get('reason')}")
            elif until_vulns and not de_state.get("vuln_found"):
                plan = _hunt_escalation_plan(
                    target,
                    completed_tools=completed_tools | failed_tools,
                    step=step,
                    posture=posture_n,
                )
                job["ai"]["steps"].append(plan)
                log(f"AI hunt escalation ({plan.get('source')}): {plan.get('reason')}")
            if plan.get("stop") or not plan.get("tools"):
                log("AI stopped planning.")
                break

        if plan.get("source") == "novel_invention":
            inventions_used += 1
            job["ai"]["inventions_used"] = inventions_used
        _register_plan_inventions(plan, job)

        tools = []
        seen_this_phase: set[str] = set()
        skip_tools = failed_tools if adaptive else set()
        for entry in plan["tools"]:
            name = entry["tool"]
            if require_confirm_for_tool(name) and not confirm_high_risk:
                log(f"Skipping high-risk tool {name} (confirm_high_risk=false)")
                continue
            if plan.get("source") != "chat_plan" and name in completed_tools and not _allows_tool_retry(plan):
                log(f"Skipping already-completed tool {name}")
                continue
            if (
                adaptive
                and name in skip_tools
                and not _allows_tool_retry(plan)
            ):
                log(f"Skipping previously failed tool {name}; trying another vector")
                continue
            if name in seen_this_phase:
                log(f"Skipping duplicate tool {name} in this phase")
                continue
            seen_this_phase.add(name)
            tools.append(entry)
        if not tools:
            if (until_vulns or adaptive) and not de_state.get("vuln_found"):
                from orchestrator.ai.target_study import build_target_profile

                plan = _adaptive_escalation_plan(
                    target,
                    nl_goal,
                    job=job,
                    completed_tools=completed_tools,
                    failed_tools=failed_tools,
                    step=step,
                    posture=posture_n,
                    profile=build_target_profile(de_state, results_by_phase),
                    decision_state=de_state,
                    inventions_used=inventions_used,
                )
                if plan.get("source") == "novel_invention":
                    inventions_used += 1
                    job["ai"]["inventions_used"] = inventions_used
                _register_plan_inventions(plan, job)
                for entry in plan.get("tools") or []:
                    name = entry["tool"]
                    if require_confirm_for_tool(name) and not confirm_high_risk:
                        log(f"Skipping high-risk tool {name} (confirm_high_risk=false)")
                        continue
                    if name in completed_tools and not _allows_tool_retry(plan):
                        continue
                    if adaptive and name in failed_tools and not _allows_tool_retry(plan):
                        continue
                    tools.append(entry)
            elif until_vulns and not de_state.get("vuln_found"):
                plan = _hunt_escalation_plan(
                    target,
                    completed_tools=completed_tools | failed_tools,
                    step=step,
                    posture=posture_n,
                )
                for entry in plan.get("tools") or []:
                    name = entry["tool"]
                    if require_confirm_for_tool(name) and not confirm_high_risk:
                        log(f"Skipping high-risk tool {name} (confirm_high_risk=false)")
                        continue
                    if name in completed_tools | failed_tools:
                        continue
                    tools.append(entry)
            if not tools:
                phase_name = _resolve_phase_name(plan, step)
                _record_empty_phase(
                    job=job,
                    job_id=job_id,
                    target=target,
                    phase_name=phase_name,
                    reason="No new tools left after dedupe/safety filter",
                    results_by_phase=results_by_phase,
                    decision_engine=decision_engine,
                    log=log,
                )
                break

        phase_name = _resolve_phase_name(plan, step)
        plan["phase_name"] = phase_name
        if job["ai"]["steps"]:
            job["ai"]["steps"][-1]["phase_name"] = phase_name
        if _cancel_requested(job_id):
            _finalize_cancellation(job, job_id, log)
            break
        phase_use_proxy = _phase_use_proxy(use_proxy, decision_engine, evasion)
        from tools.breach_intel import inject_osint_seeds_into_tools

        tools = inject_osint_seeds_into_tools(tools, job.get("osint_seeds") or osint_seeds)
        workflow = build_phase_workflow(
            phase_name,
            tools,
            target,
            parallel=bool(plan.get("parallel")),
            use_proxy=phase_use_proxy,
            proxy_protocol=proxy_protocol,
            evasion=evasion,
        )
        if workflow is None:
            _record_empty_phase(
                job=job,
                job_id=job_id,
                target=target,
                phase_name=phase_name,
                reason="No valid tools in phase",
                results_by_phase=results_by_phase,
                decision_engine=decision_engine,
                log=lambda msg: log(f"AI phase {phase_name} produced empty workflow"),
            )
            break

        from orchestrator.celery_errors import assert_workers_ready

        assert_workers_ready([entry.get("tool") for entry in tools if entry.get("tool")])
        if _cancel_requested(job_id):
            _finalize_cancellation(job, job_id, log)
            break
        async_result = workflow.apply_async()
        phase_record: dict[str, Any] = {
            "phase": phase_name,
            "task_id": async_result.id,
            "reason": plan.get("reason"),
        }
        if bool(plan.get("parallel")):
            phase_record["child_task_ids"] = _workflow_child_task_ids(async_result)
        from orchestrator.services.missions import register_phase_tasks

        authoritative = register_phase_tasks(job_id, phase_record)
        if authoritative is not None:
            job.setdefault("phases", []).append(phase_record)
            if authoritative.get("cancel_requested"):
                job["cancel_requested"] = True
            if authoritative.get("state") in {"CANCEL_REQUESTED", "CANCELLED"}:
                job["state"] = authoritative["state"]
        if _cancel_requested(job_id):
            _revoke_dispatched_tasks(phase_record)
            _finalize_cancellation(job, job_id, log)
            break
        timed_out = False
        phase_limit = _phase_timeout_seconds(phase_name, tools)
        try:
            if bool(plan.get("parallel")):
                phase_output = collect_group_results(
                    async_result, timeout=phase_limit
                )
            else:
                phase_output = collect_chain_results(
                    async_result, timeout=phase_limit
                )
        except Exception as exc:
            timed_out = (
                isinstance(exc, (CeleryTimeoutError, TimeoutError))
                or "timed out" in str(exc).lower()
            )
            phase_output = _partial_results(async_result)
            if not phase_output:
                if timed_out:
                    phase_output = [
                        {
                            "tool": "phase",
                            "error": f"phase timed out after {phase_limit}s: {exc}",
                            "partial": True,
                        }
                    ]
                else:
                    phase_output = [
                        {
                            "tool": "phase",
                            "error": str(exc),
                            "partial": True,
                        }
                    ]
            if timed_out:
                log(
                    f"AI phase {phase_name} timed out after {phase_limit}s; continuing with "
                    f"{len(phase_output)} partial result(s)"
                )
            else:
                log(
                    f"AI phase {phase_name} failed during collection; continuing with "
                    f"{len(phase_output)} partial result(s): {exc}"
                )
            try:
                async_result.revoke(terminate=True, signal="SIGKILL")
            except Exception:
                pass

        results_by_phase[phase_name] = phase_output
        _record_phase_outcomes(
            tools,
            phase_output,
            completed_tools=completed_tools,
            failed_tools=failed_tools,
        )
        from orchestrator.services.missions import merge_phase_result

        authoritative = merge_phase_result(
            job_id, phase_name, phase_output, sorted(failed_tools)
        )
        if authoritative is not None:
            job["cancel_requested"] = bool(authoritative.get("cancel_requested"))
            job["state"] = authoritative.get("state") or job.get("state")
        else:
            job.setdefault("results", {})[phase_name] = phase_output
            job.setdefault("ai", {})["failed_tools"] = sorted(failed_tools)
        save_phase_result(
            target,
            phase_name,
            phase_output,
            job_id=job_id,
            org_id=job.get("org_id"),
        )
        if _cancel_requested(job_id):
            _finalize_cancellation(job, job_id, log)
            break
        try:
            from orchestrator.ai import blackboard

            blackboard.put(
                job_id,
                f"phase:{phase_name}",
                {
                    "tools": [
                        (i.get("tool") if isinstance(i, dict) else None)
                        for i in (
                            phase_output if isinstance(phase_output, list) else [phase_output]
                        )
                    ],
                    "count": len(phase_output)
                    if isinstance(phase_output, list)
                    else 1,
                },
                org_id=job.get("org_id"),
            )
            # Compact findings strip for UI
            digest = []
            for item in phase_output if isinstance(phase_output, list) else [phase_output]:
                if not isinstance(item, dict):
                    continue
                row = {"tool": item.get("tool")}
                if item.get("ports"):
                    row["ports"] = len(item["ports"])
                if item.get("error"):
                    row["error"] = str(item["error"])[:120]
                digest.append(row)
            blackboard.put(
                job_id,
                "findings",
                {"phases": list(results_by_phase.keys()), "latest": digest},
                org_id=job.get("org_id"),
            )
        except Exception:
            pass
        decision_engine.evaluate_phase(phase_name, phase_output)
        if _cancel_requested(job_id):
            _finalize_cancellation(job, job_id, log)
            break
        _run_post_phase_actions(
            decision_engine=decision_engine,
            phase_name=phase_name,
            phase_output=phase_output,
            job=job,
            job_id=job_id,
            target=target,
            use_proxy=_phase_use_proxy(use_proxy, decision_engine, evasion),
            proxy_protocol=proxy_protocol,
            evasion=evasion,
            results_by_phase=results_by_phase,
            add_log=log,
        )
        de_state = getattr(decision_engine, "state", None) or {}
        if (until_vulns or adaptive) and de_state.get("vuln_found"):
            log("Vulnerabilities confirmed — adaptive attack goal met.")
            job["ai"]["vuln_found"] = True
            break
        if timed_out:
            # Prefer a re-plan that avoids repeating the hung tool set.
            continue

    summary = (
        f"goal={nl_goal or 'default'} posture={posture_n} "
        f"phases={list(results_by_phase.keys())}"
    )
    try:
        memory.remember(summary, target_hint=target)
    except Exception:
        pass
    recs = hardening_recommendations(results_by_phase, posture=posture_n)
    finished_at = time.time()
    from orchestrator.services.missions import merge_runner_completion

    authoritative = merge_runner_completion(
        job_id, hardening=recs, finished_at=finished_at
    )
    if authoritative is not None:
        job.update(authoritative)
    else:
        job.setdefault("ai", {})["hardening"] = recs
        job["ai"]["finished_at"] = finished_at
    try:
        from orchestrator.ai import blackboard

        blackboard.put(
            job_id,
            "hardening",
            {"recommendations": recs, "posture": posture_n},
            org_id=job.get("org_id"),
        )
        blackboard.put(
            job_id,
            "findings.summary",
            {
                "phases": list(results_by_phase.keys()),
                "posture": posture_n,
                "hardening_count": len(recs),
            },
            org_id=job.get("org_id"),
        )
    except Exception:
        pass
