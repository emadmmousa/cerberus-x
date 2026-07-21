"""Auth0 SDK wiring tests (no live Auth0 calls)."""

from security.auth0_sdk import auth0_configured, auth0_status, reset_auth0_client
from orchestrator import dashboard


def test_auth0_not_configured_by_default(monkeypatch):
    monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
    monkeypatch.delenv("AUTH0_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH0_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AUTH0_SECRET", raising=False)
    reset_auth0_client()
    assert auth0_configured() is False
    st = auth0_status()
    assert st["login_path"] == "/auth/sso"
    assert st["callback_path"] == "/callback"
    assert st["configured"] is False
    assert "AUTH0_DOMAIN" in st["missing"]


def test_auth0_configured_when_env_set(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "example.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "cid")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "csec")
    monkeypatch.setenv("AUTH0_SECRET", "x" * 64)
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:5000")
    reset_auth0_client()
    assert auth0_configured() is True
    st = auth0_status()
    assert st["callback_url"] == "http://localhost:5000/callback"
    assert st["domain"] == "example.auth0.com"


def test_login_returns_503_when_unconfigured(monkeypatch):
    monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
    monkeypatch.delenv("AUTH0_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH0_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AUTH0_SECRET", raising=False)
    reset_auth0_client()
    client = dashboard.app.test_client()
    resp = client.get("/auth/sso")
    assert resp.status_code == 503


def test_api_oidc_status_prefers_auth0_shape_when_configured(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", "example.auth0.com")
    monkeypatch.setenv("AUTH0_CLIENT_ID", "cid")
    monkeypatch.setenv("AUTH0_CLIENT_SECRET", "csec")
    monkeypatch.setenv("AUTH0_SECRET", "y" * 64)
    reset_auth0_client()
    client = dashboard.app.test_client()
    data = client.get("/api/oidc/status").get_json()
    assert data["provider"] == "auth0"
    assert data["configured"] is True
    assert data["login_path"] == "/auth/sso"
