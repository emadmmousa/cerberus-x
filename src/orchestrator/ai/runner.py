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
    max_steps: int = 5,
    add_log: Optional[LogFn] = None,
) -> None:
    """
    Adaptive loop: plan → execute phase tools → evaluate → re-plan.
    High-risk tools in the plan are skipped unless confirm_high_risk is True
    (Celery enqueue path still enforces confirm for MCP; here we filter tools).
    """
    log = add_log or (lambda msg: None)
    from orchestrator.ai.safety import is_high_risk

    decision_engine = DecisionEngine(target, job_id=job_id)
    results_by_phase: dict[str, Any] = {}
    job["ai"] = {"goal": nl_goal, "steps": [], "mode": "ai"}

    for step in range(max_steps):
        plan = planner.suggest_next_phase(
            target, results_by_phase, nl_goal=nl_goal, step=step
        )
        job["ai"]["steps"].append(plan)
        log(f"AI plan ({plan.get('source')}): {plan.get('reason')}")

        if plan.get("stop") or not plan.get("tools"):
            log("AI stopped planning.")
            break

        tools = []
        for entry in plan["tools"]:
            name = entry["tool"]
            if is_high_risk(name) and not confirm_high_risk:
                log(f"Skipping high-risk tool {name} (confirm_high_risk=false)")
                continue
            tools.append(entry)
        if not tools:
            log("No runnable tools after safety filter; stopping.")
            break

        phase_name = plan["phase_name"] or f"ai_step_{step}"
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
        save_phase_result(target, phase_name, phase_output, job_id=job_id)
        decision_engine.evaluate_phase(phase_name, phase_output)
        if timed_out:
            # Prefer a re-plan that avoids repeating the hung tool set.
            continue

    summary = (
        f"target={target} goal={nl_goal or 'default'} "
        f"phases={list(results_by_phase.keys())}"
    )
    try:
        memory.remember(summary, target_hint=target)
    except Exception:
        pass
    job["ai"]["finished_at"] = time.time()
