"""Celery task dispatch helpers and operator-facing error text."""

from __future__ import annotations

import os
import re
from typing import Iterable

from celery.exceptions import NotRegistered

from orchestrator.ai.scaffold_tools import (
    EXPECTED_SCAFFOLD_COUNT,
    is_scaffold_tool,
    scaffold_tool_names,
)

_UNREGISTERED_TASK_RE = re.compile(
    r"^['\"]?orchestrator\.tasks\.run_[a-z0-9_]+_task['\"]?$",
    re.IGNORECASE,
)


def _worker_preflight_enabled() -> bool:
    return os.getenv("FIREBREAK_WORKER_PREFLIGHT", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def format_celery_collect_error(exc: BaseException) -> str:
    """Turn opaque Celery worker registry failures into actionable text."""
    if isinstance(exc, NotRegistered):
        task = getattr(exc, "name", None) or str(exc)
        return _worker_restart_message(task)

    text = str(exc).strip()
    if _UNREGISTERED_TASK_RE.match(text) or (
        text.startswith("orchestrator.tasks.run_") and text.endswith("_task")
    ):
        return _worker_restart_message(text)
    return text


def _worker_restart_message(task_or_tool: str) -> str:
    return (
        f"Worker does not have task {task_or_tool} registered. "
        "Restart Celery workers after code changes: docker compose restart worker"
    )


def unique_task_map_celery_names() -> set[str]:
    """Distinct Celery task names backing the wired CLI + scaffold/* arsenal."""
    from orchestrator.tasks import _TASK_MAP

    names = {
        getattr(task_fn, "name", None)
        for task_fn in _TASK_MAP.values()
        if getattr(task_fn, "name", None)
    }
    return names


def _worker_registered_tasks(timeout: float = 3.0) -> set[str] | None:
    from orchestrator.celery_app import app

    try:
        inspect = app.control.inspect(timeout=timeout)
        if inspect is None:
            return None
        registered_payload = inspect.registered()
    except Exception:
        # Celery/kombu may surface broker and control-channel failures through
        # several transport-specific exception types. Readiness treats all of
        # them as an unreachable registry rather than failing the endpoint.
        return None

    if registered_payload is None:
        return None

    registered: set[str] = set()
    for tasks in registered_payload.values():
        registered.update(tasks or [])
    return registered


def worker_readiness(timeout: float = 3.0) -> dict[str, object]:
    """Summarize whether live workers expose the current task registry."""
    registered = _worker_registered_tasks(timeout=timeout)
    expected = unique_task_map_celery_names()
    if registered is None:
        return {
            "status": "unreachable",
            "expected_count": len(expected),
            "missing_tasks": [],
        }

    missing = sorted(expected - registered)
    return {
        "status": "stale" if missing else "ready",
        "expected_count": len(expected),
        "missing_tasks": missing,
        "message": (
            format_missing_celery_tasks_error(missing)
            if missing
            else "Workers ready"
        ),
    }


def missing_registered_celery_tasks(timeout: float = 3.0) -> list[str]:
    """Return Celery task names from ``_TASK_MAP`` that no live worker exposes."""
    registered = _worker_registered_tasks(timeout=timeout)
    if registered is None:
        return []

    required = unique_task_map_celery_names()
    return sorted(name for name in required if name not in registered)


def missing_registered_tools(tool_names: Iterable[str], timeout: float = 3.0) -> list[str]:
    """Return logical tools whose Celery tasks are absent from all live workers."""
    from orchestrator.tasks import _TASK_MAP, run_scaffold_bundle_task

    registered = _worker_registered_tasks(timeout=timeout)
    if registered is None:
        return []

    missing: list[str] = []
    scaffold_bundle_name = getattr(run_scaffold_bundle_task, "name", None)
    for tool in tool_names:
        if not tool:
            continue
        task_fn = _TASK_MAP.get(tool)
        if task_fn is None:
            continue
        task_name = getattr(task_fn, "name", None)
        if task_name and task_name not in registered:
            missing.append(tool)

    if scaffold_bundle_name and scaffold_bundle_name not in registered:
        for name in sorted(scaffold_tool_names()):
            if name not in missing:
                missing.append(name)
    return sorted(set(missing))


def format_missing_tools_error(tools: list[str]) -> str:
    scaffolds = [tool for tool in tools if is_scaffold_tool(tool)]
    cli_tools = [tool for tool in tools if tool and not is_scaffold_tool(tool)]
    parts: list[str] = []
    if cli_tools:
        parts.append(", ".join(sorted(set(cli_tools))))
    if scaffolds:
        parts.append(
            f"{len(scaffolds)} scaffold/* bundles "
            f"(expected {EXPECTED_SCAFFOLD_COUNT}, via run_scaffold_bundle_task)"
        )
    joined = "; ".join(parts) if parts else ", ".join(sorted(set(tools)))
    return (
        f"Worker is missing tool task(s): {joined}. "
        "Restart Celery workers after code changes: docker compose restart worker"
    )


def format_missing_celery_tasks_error(task_names: list[str]) -> str:
    joined = ", ".join(task_names)
    return (
        f"Worker is missing Celery task(s): {joined}. "
        f"The wired arsenal covers {EXPECTED_SCAFFOLD_COUNT} scaffold/* bundles plus "
        "41 CLI wrappers. Restart workers after code changes: "
        "docker compose restart worker"
    )


def assert_workers_ready(tool_names: list[str], timeout: float = 3.0) -> None:
    """Fail fast when live workers are stale and missing newly added tasks."""
    if not _worker_preflight_enabled():
        return
    missing = missing_registered_tools(tool_names, timeout=timeout)
    if missing:
        raise RuntimeError(format_missing_tools_error(missing))


def assert_full_arsenal_ready(timeout: float = 3.0) -> None:
    """Verify every unique Celery executor backing the wired arsenal is registered."""
    if not _worker_preflight_enabled():
        return
    missing_tasks = missing_registered_celery_tasks(timeout=timeout)
    if missing_tasks:
        raise RuntimeError(format_missing_celery_tasks_error(missing_tasks))
