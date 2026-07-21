"""Wave 5 Pro packaging readiness tests."""

from security.pro_packaging import packaging_status, sso_readiness


def test_sso_not_ready_by_default(monkeypatch):
    for key in (
        "AUTH0_DOMAIN",
        "AUTH0_CLIENT_ID",
        "AUTH0_CLIENT_SECRET",
        "AUTH0_SECRET",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_ISSUER",
    ):
        monkeypatch.delenv(key, raising=False)
    sso = sso_readiness()
    assert sso["ready"] is False
    assert sso["preferred"] is None
    assert "AUTH0_DOMAIN" in sso["auth0"]["missing"]


def test_sso_ready_with_auth0(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "example.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "cid")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "csec")
    monkeypatch.setenv("AUTH0_SECRET", "z" * 64)
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:5000")
    sso = sso_readiness()
    assert sso["ready"] is True
    assert sso["preferred"] == "auth0"
    assert sso["auth0"]["missing"] == []


def test_edition_status_endpoint(monkeypatch):
    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    monkeypatch.setenv("FIREBREAK_MANAGED_HOSTING", "true")
    from orchestrator import dashboard

    client = dashboard.app.test_client()
    resp = client.get("/api/edition/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["edition"] == "pro"
    assert data["managed_hosting"]["enabled"] is True
    assert "sso" in data


def test_packaging_status_community_default(monkeypatch):
    monkeypatch.delenv("FIREBREAK_EDITION", raising=False)
    monkeypatch.delenv("FIREBREAK_MANAGED_HOSTING", raising=False)
    status = packaging_status()
    assert status["edition"] == "community"
    assert status["managed_hosting"]["enabled"] is False
