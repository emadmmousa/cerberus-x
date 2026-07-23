"""Celery worker registry error formatting."""

from celery.exceptions import NotRegistered

from orchestrator.ai.scaffold_tools import EXPECTED_SCAFFOLD_COUNT, scaffold_tool_name
from orchestrator.celery_errors import (
    assert_full_arsenal_ready,
    assert_workers_ready,
    format_celery_collect_error,
    format_missing_celery_tasks_error,
    format_missing_tools_error,
    missing_registered_celery_tasks,
    missing_registered_tools,
    unique_task_map_celery_names,
)
from orchestrator.tasks import _TASK_MAP, run_scaffold_bundle_task


def test_format_not_registered_exception():
    err = format_celery_collect_error(
        NotRegistered("orchestrator.tasks.run_amass_task")
    )
    assert "run_amass_task" in err
    assert "docker compose restart worker" in err


def test_format_bare_task_name_string():
    err = format_celery_collect_error(
        Exception("'orchestrator.tasks.run_amass_task'")
    )
    assert "run_amass_task" in err
    assert "docker compose restart worker" in err


def test_format_missing_tools_error_lists_tools():
    msg = format_missing_tools_error(["amass", "naabu"])
    assert "amass" in msg
    assert "naabu" in msg
    assert "docker compose restart worker" in msg


def test_format_missing_tools_error_groups_scaffolds():
    msg = format_missing_tools_error(
        [scaffold_tool_name("sql-injection"), scaffold_tool_name("xss-hunter")]
    )
    assert "scaffold/* bundles" in msg
    assert str(EXPECTED_SCAFFOLD_COUNT) in msg
    assert "run_scaffold_bundle_task" in msg


def test_assert_workers_ready_raises(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.celery_errors.missing_registered_tools",
        lambda names, timeout=3.0: ["amass"],
    )
    try:
        assert_workers_ready(["amass"])
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "amass" in str(exc)


def test_missing_registered_tools_without_workers(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.celery_errors._worker_registered_tasks",
        lambda timeout=3.0: None,
    )
    assert missing_registered_tools(["amass"]) == []


def test_missing_registered_tools_expands_all_scaffolds_when_bundle_missing(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.celery_errors._worker_registered_tasks",
        lambda timeout=3.0: set(),
    )
    missing = missing_registered_tools([scaffold_tool_name("nuclei-runner")])
    assert len(missing) == EXPECTED_SCAFFOLD_COUNT
    assert scaffold_tool_name("sql-injection") in missing


def test_unique_task_map_covers_cli_and_scaffold_executor():
    names = unique_task_map_celery_names()
    assert "orchestrator.tasks.run_amass_task" in names
    assert "orchestrator.tasks.run_scaffold_bundle_task" in names
    assert len(names) == 42
    assert len(_TASK_MAP) == 41 + EXPECTED_SCAFFOLD_COUNT


def test_all_scaffolds_map_to_bundle_executor():
    scaffolds = {key for key in _TASK_MAP if key.startswith("scaffold/")}
    assert len(scaffolds) == EXPECTED_SCAFFOLD_COUNT
    assert all(_TASK_MAP[name] is run_scaffold_bundle_task for name in scaffolds)


def test_assert_full_arsenal_ready_raises(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.celery_errors.missing_registered_celery_tasks",
        lambda timeout=3.0: ["orchestrator.tasks.run_scaffold_bundle_task"],
    )
    try:
        assert_full_arsenal_ready()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "run_scaffold_bundle_task" in str(exc)
        assert str(EXPECTED_SCAFFOLD_COUNT) in str(exc)


def test_missing_registered_celery_tasks_without_workers(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.celery_errors._worker_registered_tasks",
        lambda timeout=3.0: None,
    )
    assert missing_registered_celery_tasks() == []


def test_format_missing_celery_tasks_error():
    msg = format_missing_celery_tasks_error(
        ["orchestrator.tasks.run_scaffold_bundle_task"]
    )
    assert "run_scaffold_bundle_task" in msg
    assert str(EXPECTED_SCAFFOLD_COUNT) in msg
