"""AI mission runner (Phases 2–4)."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from celery.exceptions import TimeoutError as CeleryTimeoutError

from orchestrator.ai import memory, planner
from orchestrator.cli import collect_chain_results, collect_group_results
from orchestrator.database import save_phase_result
from orchestrator.decision_engine import DecisionEngine
from orchestrator.tasks import build_phase_workflow


LogFn = Callable[[str], None]

# Per-phase wait for Celery group/chain. Keep below pathological tool hangs;
# masscan/etc. also have their own soft time limits.
PHASE_TIMEOUT_SECONDS = 180


def _partial_results(async_result) -> list[Any]:
    """Best-effort gather of finished children after a phase timeout."""
    collected: list[Any] = []
    try:
        children = list(async_result.children or [])
    except Exception:
        children = []
    for child in children:
        try:
            if child.successful():
                collected.append(child.result)
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
    posture: str = "balanced",
    max_steps: int = 5,
    add_log: Optional[LogFn] = None,
) -> None:
    """
    Adaptive loop: plan → execute phase tools → evaluate → re-plan.
    High-risk tools in the plan are skipped unless confirm_high_risk is True
    (Celery enqueue path still enforces confirm for MCP; here we filter tools).
    """
    log = add_log or (lambda msg: None)
    from orchestrator.ai.safety import require_confirm_for_tool
    from orchestrator.ai.posture import hardening_recommendations, normalize_posture

    posture_n = normalize_posture(posture)
    decision_engine = DecisionEngine(target, job_id=job_id, posture=posture_n)
    results_by_phase: dict[str, Any] = {}
    completed_tools: set[str] = set()
    job["ai"] = {"goal": nl_goal, "steps": [], "mode": "ai", "posture": posture_n}

    for step in range(max_steps):
        plan = planner.suggest_next_phase(
            target,
            results_by_phase,
            nl_goal=nl_goal,
            step=step,
            posture=posture_n,
            mission_id=job_id,
        )
        job["ai"]["steps"].append(plan)
        log(f"AI plan ({plan.get('source')}): {plan.get('reason')}")
        try:
            from orchestrator.job_store import playbook_jobs

            playbook_jobs.persist(job_id)
        except Exception:
            pass

        if plan.get("stop") or not plan.get("tools"):
            log("AI stopped planning.")
            break

        tools = []
        seen_this_phase: set[str] = set()
        for entry in plan["tools"]:
            name = entry["tool"]
            # When FIREBREAK_AI_REQUIRE_CONFIRM=false, high-risk tools always run.
            if require_confirm_for_tool(name) and not confirm_high_risk:
                log(f"Skipping high-risk tool {name} (confirm_high_risk=false)")
                continue
            if name in completed_tools or name in seen_this_phase:
                log(f"Skipping already-completed tool {name}")
                continue
            seen_this_phase.add(name)
            tools.append(entry)
        if not tools:
            log("No new tools left after dedupe/safety filter; stopping.")
            break

        phase_name = plan["phase_name"] or f"ai_step_{step}"
        if step > 0 and not phase_name.endswith(f"_s{step}"):
            phase_name = f"{phase_name}_s{step}"
        workflow = build_phase_workflow(
            phase_name,
            tools,
            target,
            parallel=bool(plan.get("parallel")),
            use_proxy=use_proxy,
            proxy_protocol=proxy_protocol,
            evasion=evasion,
        )
        if workflow is None:
            log(f"AI phase {phase_name} produced empty workflow")
            break

        async_result = workflow.apply_async()
        job.setdefault("phases", []).append(
            {"phase": phase_name, "task_id": async_result.id, "reason": plan.get("reason")}
        )
        timed_out = False
        try:
            if bool(plan.get("parallel")):
                phase_output = collect_group_results(
                    async_result, timeout=PHASE_TIMEOUT_SECONDS
                )
            else:
                phase_output = collect_chain_results(
                    async_result, timeout=PHASE_TIMEOUT_SECONDS
                )
        except Exception as exc:
            # Celery raises celery.exceptions.TimeoutError; some paths use builtins.
            if not (
                isinstance(exc, (CeleryTimeoutError, TimeoutError))
                or "timed out" in str(exc).lower()
            ):
                raise
            timed_out = True
            phase_output = _partial_results(async_result)
            if not phase_output:
                phase_output = [
                    {
                        "tool": "phase",
                        "error": f"phase timed out after {PHASE_TIMEOUT_SECONDS}s: {exc}",
                        "partial": True,
                    }
                ]
            log(
                f"AI phase {phase_name} timed out; continuing with "
                f"{len(phase_output)} partial result(s)"
            )
            try:
                async_result.revoke(terminate=True, signal="SIGKILL")
            except Exception:
                pass

        results_by_phase[phase_name] = phase_output
        job.setdefault("results", {})[phase_name] = phase_output
        for item in phase_output if isinstance(phase_output, list) else [phase_output]:
            if isinstance(item, dict) and item.get("tool") and item["tool"] != "phase":
                completed_tools.add(str(item["tool"]))
        # Also mark planned tools that returned as completed even if payload lacked tool key.
        for entry in tools:
            completed_tools.add(entry["tool"])
        save_phase_result(
            target,
            phase_name,
            phase_output,
            job_id=job_id,
            org_id=job.get("org_id"),
        )
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
    job["ai"]["hardening"] = recs
    job["ai"]["finished_at"] = time.time()
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
    try:
        from orchestrator.job_store import playbook_jobs

        playbook_jobs.persist(job_id)
    except Exception:
        pass
