"""Worker readiness and synchronous mission-launch preflight tests."""

from orchestrator import dashboard
from orchestrator.job_store import playbook_jobs


def test_worker_readiness_marks_unreachable(monkeypatch):
    from orchestrator import celery_app, celery_errors

    monkeypatch.setattr(
        celery_errors, "unique_task_map_celery_names", lambda: {"expected.task"}
    )
    monkeypatch.setattr(
        celery_app.app.control,
        "inspect",
        lambda timeout: type(
            "InspectReply",
            (),
            {"registered": lambda self: None},
        )(),
    )

    payload = celery_errors.worker_readiness()

    assert payload["status"] == "unreachable"
    assert payload["expected_count"] == 1
    assert payload["missing_tasks"] == []


def test_worker_readiness_marks_inspection_exception_unreachable(monkeypatch):
    from orchestrator import celery_app, celery_errors

    class FailedInspect:
        def registered(self):
            raise ConnectionError("broker unavailable")

    monkeypatch.setattr(
        celery_errors, "unique_task_map_celery_names", lambda: {"expected.task"}
    )
    monkeypatch.setattr(
        celery_app.app.control,
        "inspect",
        lambda timeout: FailedInspect(),
    )

    assert celery_errors.worker_readiness()["status"] == "unreachable"


def test_worker_readiness_marks_reachable_empty_registry_stale(monkeypatch):
    from orchestrator import celery_app, celery_errors

    monkeypatch.setattr(
        celery_errors, "unique_task_map_celery_names", lambda: {"expected.task"}
    )
    monkeypatch.setattr(
        celery_app.app.control,
        "inspect",
        lambda timeout: type(
            "InspectReply",
            (),
            {"registered": lambda self: {"celery@worker": []}},
        )(),
    )

    payload = celery_errors.worker_readiness()

    assert payload["status"] == "stale"
    assert payload["missing_tasks"] == ["expected.task"]


def test_worker_readiness_marks_stale_and_lists_missing_tasks(monkeypatch):
    from orchestrator import celery_errors

    expected = {"orchestrator.tasks.run_alpha_task", "orchestrator.tasks.run_beta_task"}
    monkeypatch.setattr(celery_errors, "unique_task_map_celery_names", lambda: expected)
    monkeypatch.setattr(
        celery_errors,
        "_worker_registered_tasks",
        lambda timeout: {"orchestrator.tasks.run_alpha_task"},
    )

    payload = celery_errors.worker_readiness(timeout=1.5)

    assert payload["status"] == "stale"
    assert payload["expected_count"] == 2
    assert payload["missing_tasks"] == ["orchestrator.tasks.run_beta_task"]
    assert "run_beta_task" in payload["message"]


def test_worker_readiness_marks_ready(monkeypatch):
    from orchestrator import celery_errors

    expected = {"orchestrator.tasks.run_alpha_task"}
    monkeypatch.setattr(celery_errors, "unique_task_map_celery_names", lambda: expected)
    monkeypatch.setattr(
        celery_errors,
        "_worker_registered_tasks",
        lambda timeout: expected,
    )

    assert celery_errors.worker_readiness() == {
        "status": "ready",
        "expected_count": 1,
        "missing_tasks": [],
        "message": "Workers ready",
    }


def test_api_run_preflight_failure_creates_no_job(monkeypatch):
    import orchestrator.api.missions as missions_api

    monkeypatch.setattr(
        missions_api,
        "assert_full_arsenal_ready",
        lambda: (_ for _ in ()).throw(RuntimeError("missing task")),
    )
    before = set(playbook_jobs)

    response = dashboard.app.test_client().post(
        "/api/run",
        json={"target": "authorized.example"},
    )

    assert response.status_code == 503
    assert response.get_json() == {
        "error": "missing task",
        "reason": "worker_preflight_failed",
    }
    assert set(playbook_jobs) == before


def test_worker_readiness_endpoint_requires_viewer_when_rbac_enabled(monkeypatch):
    import orchestrator.api.missions as missions_api

    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "true")
    monkeypatch.setattr("security.rbac.rbac_enforce_enabled", lambda: True)
    monkeypatch.setattr(
        missions_api,
        "worker_readiness",
        lambda: {
            "status": "ready",
            "expected_count": 1,
            "missing_tasks": [],
            "message": "Workers ready",
        },
    )
    client = dashboard.app.test_client()

    assert client.get("/api/workers/readiness").status_code == 401

    with client.session_transaction() as session:
        session["user"] = "viewer@example.com"
        session["role"] = "viewer"
        session["org_id"] = "default"
        session["auth_method"] = "local"

    response = client.get("/api/workers/readiness")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"
