"""Org-scoped results + OIDC apply_claims tests."""

from security.oidc import apply_oidc_claims, oidc_status
from orchestrator import database


def test_save_and_get_results_org(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "r.db"))
    monkeypatch.setattr(
        database,
        "export_target_reports",
        lambda *a, **k: {"json": "x.json", "html": "x.html"},
    )
    database.save_phase_result(
        "https://a.example",
        "recon",
        [{"tool": "nmap", "ports": []}],
        job_id="j1",
        org_id="org-a",
    )
    database.save_phase_result(
        "https://a.example",
        "recon",
        [{"tool": "nmap", "ports": []}],
        job_id="j2",
        org_id="org-b",
    )
    a = database.get_results(target="https://a.example", org_id="org-a")
    b = database.get_results(target="https://a.example", org_id="org-b")
    assert len(a) == 1
    assert a[0]["org_id"] == "org-a"
    assert len(b) == 1
    assert b[0]["org_id"] == "org-b"


def test_apply_oidc_claims(monkeypatch):
    from flask import Flask, session

    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/"):
        profile = apply_oidc_claims(
            {"email": "op@lab.example", "firebreak_role": "admin", "org_id": "acme"}
        )
        assert profile["user"] == "op@lab.example"
        assert profile["role"] == "admin"
        assert profile["org_id"] == "acme"
        assert session["user"] == "op@lab.example"


def test_oidc_status_paths():
    st = oidc_status()
    assert st["login_path"] == "/auth/oidc/login"
    assert st["callback_path"] == "/auth/oidc/callback"
