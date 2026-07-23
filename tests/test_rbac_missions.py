"""RBAC + org isolation for Mission Control shell APIs."""

import pytest

from orchestrator import dashboard
from orchestrator.job_store import playbook_jobs


@pytest.fixture(autouse=True)
def clear_persisted_rbac_override():
    from security import admin_store

    previous = admin_store.rbac_enforce_override()
    admin_store.set_rbac_enforce(None)
    yield
    admin_store.set_rbac_enforce(previous)


def test_missions_list_org_scoped(monkeypatch):
    playbook_jobs.clear() if hasattr(playbook_jobs, "clear") else None
    playbook_jobs._local.clear()
    playbook_jobs["job-a"] = {
        "task_id": "job-a",
        "target": "a.example",
        "state": "SUCCESS",
        "org_id": "org-a",
        "phases": [],
    }
    playbook_jobs["job-b"] = {
        "task_id": "job-b",
        "target": "b.example",
        "state": "SUCCESS",
        "org_id": "org-b",
        "phases": [],
    }
    client = dashboard.app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "operator"
        sess["org_id"] = "org-a"
        sess["auth_method"] = "local"
    data = client.get("/api/missions").get_json()
    ids = {m["task_id"] for m in data["missions"]}
    assert "job-a" in ids
    assert "job-b" not in ids


def test_status_forbidden_other_org_when_rbac_on(monkeypatch):
    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "true")
    playbook_jobs._local.clear()
    playbook_jobs["secret-job"] = {
        "task_id": "secret-job",
        "target": "x.example",
        "state": "SUCCESS",
        "org_id": "other",
        "phases": [],
    }
    client = dashboard.app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "alice"
        sess["role"] = "operator"
        sess["org_id"] = "default"
        sess["auth_method"] = "local"
    resp = client.get("/status/secret-job")
    assert resp.status_code == 403


def test_run_requires_auth_when_rbac_on(monkeypatch):
    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "true")
    client = dashboard.app.test_client()
    resp = client.post("/api/run", json={"target": "example.com"})
    assert resp.status_code == 401


def test_viewer_cannot_run_when_rbac_on(monkeypatch):
    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "true")
    client = dashboard.app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "bob"
        sess["role"] = "viewer"
        sess["org_id"] = "default"
        sess["auth_method"] = "local"
    resp = client.post("/api/run", json={"target": "example.com"})
    assert resp.status_code == 403


def test_rbac_me_enriched():
    client = dashboard.app.test_client()
    data = client.get("/api/rbac/me").get_json()
    assert "rbac_enforce" in data
    assert "edition" in data
    assert "role" in data


def test_role_header_ignored_unless_service_flag(monkeypatch):
    monkeypatch.setenv("FIREBREAK_RBAC_ENFORCE", "true")
    monkeypatch.delenv("FIREBREAK_SERVICE_ROLE_HEADER", raising=False)
    client = dashboard.app.test_client()
    with client.session_transaction() as sess:
        sess["user"] = "bob"
        sess["role"] = "viewer"
        sess["org_id"] = "default"
        sess["auth_method"] = "local"
    resp = client.post(
        "/api/run",
        json={"target": "example.com"},
        headers={"X-Firebreak-Role": "admin"},
    )
    assert resp.status_code == 403
