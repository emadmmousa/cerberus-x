"""MCP tool actions: enqueue Celery tasks and read results."""

from __future__ import annotations

import time
from typing import Any, Optional

from celery.result import AsyncResult

from orchestrator.ai.safety import require_confirm_for_tool
from orchestrator.celery_app import app as celery_app
from orchestrator.celery_errors import assert_workers_ready
from orchestrator.database import get_results
from orchestrator.mcp import sessions
from orchestrator.mcp.registry import HIGH_RISK, known_tools
from orchestrator.tasks import _PROXY_TOOLS, _TASK_MAP
from scanner import enforce_launch_authorization


class WorkerPreflightError(RuntimeError):
    """Requested tool is unavailable on the active workers."""


def _normalize_args(args: Any) -> list:
    if args is None:
        return []
    if isinstance(args, list):
        out = []
        for item in args:
            if isinstance(item, (str, int, float, bool)):
                out.append(str(item) if not isinstance(item, str) else item)
            else:
                raise ValueError("args items must be scalars")
        return out
    raise ValueError("args must be a list of strings")


def enqueue_tool(
    *,
    session_id: str,
    tool: str,
    target: str,
    args: Any = None,
    use_proxy: bool = False,
    proxy_protocol: str = "http",
    evasion: Optional[dict] = None,
    confirm: bool = False,
) -> dict:
    if not sessions.get_session(session_id):
        raise PermissionError("invalid session_id")
    if not sessions.check_rate_limit(session_id):
        raise RuntimeError("rate limit exceeded")
    tool = (tool or "").strip()
    target = (target or "").strip()
    if not target:
        raise ValueError("target is required")
    if tool not in known_tools():
        raise ValueError(f"unknown tool: {tool}")
    if require_confirm_for_tool(tool) and not confirm:
        raise PermissionError(
            f"high-risk tool '{tool}' requires confirm=true"
        )

    enforce_launch_authorization(target, path="mcp.run_tool")
    try:
        assert_workers_ready([tool])
    except RuntimeError as exc:
        raise WorkerPreflightError(str(exc)) from exc

    normalized = _normalize_args(args)
    evasion = evasion or {}
    task_fn = _TASK_MAP[tool]
    if tool in _PROXY_TOOLS:
        async_result = task_fn.delay(
            target, normalized, use_proxy, proxy_protocol, evasion
        )
    else:
        async_result = task_fn.delay(target, normalized, evasion)

    event = {
        "action": "run_tool",
        "tool": tool,
        "target": target,
        "task_id": async_result.id,
        "risk": "high" if tool in HIGH_RISK else "low",
        "confirm": bool(confirm),
    }
    sessions.audit(session_id, event)
    return {
        "task_id": async_result.id,
        "tool": tool,
        "target": target,
        "accepted_at": time.time(),
    }


def task_status(session_id: str, task_id: str) -> dict:
    if not sessions.get_session(session_id):
        raise PermissionError("invalid session_id")
    result = AsyncResult(task_id, app=celery_app)
    payload: dict[str, Any] = {
        "task_id": task_id,
        "state": result.state,
    }
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    sessions.audit(
        session_id,
        {"action": "get_job_status", "task_id": task_id, "state": result.state},
    )
    return payload


def findings(
    session_id: str,
    target: str,
    *,
    job_id: Optional[str] = None,
    tool: Optional[str] = None,
    phase: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    if not sessions.get_session(session_id):
        raise PermissionError("invalid session_id")
    rows = get_results(target=target, limit=limit, job_id=job_id)
    if tool:
        rows = [r for r in rows if r.get("tool") == tool]
    if phase:
        rows = [r for r in rows if r.get("phase") == phase]
    sessions.audit(
        session_id,
        {
            "action": "get_findings",
            "target": target,
            "count": len(rows),
            "tool": tool,
            "phase": phase,
        },
    )
    return rows
