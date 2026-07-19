import pytest

from tools import proxy_config, proxy_settings


@pytest.fixture(autouse=True)
def _memory_proxy_settings(monkeypatch):
    monkeypatch.setenv("CERBERUS_PROXY_SETTINGS_BACKEND", "memory")
    proxy_settings._memory_clear()
    yield
    proxy_settings._memory_clear()


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=False)
    assert result["mode"] == "direct"
    assert result["flags"] == []
    assert result["env"] == {}
    assert result["local_proxy_url"] is None


def test_default_protocol_http(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p@ss:word")
    monkeypatch.setenv("CERBERUS_LOCAL_PROXY_PORT", "18080")
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=True)
    assert result["mode"] == "local_proxy"
    assert result["local_proxy_url"] == "http://127.0.0.1:18080"
    assert "--proxy" in result["flags"]
    assert "p@ss:word" not in " ".join(result["flags"])


def test_redact_proxy_url():
    url = "http://user:secret@pr.oxylabs.io:7777"
    assert proxy_config.redact_proxy_url(url) == "http://user:***@pr.oxylabs.io:7777"


def test_upstream_url_encodes_password(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "customer-x")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p@ss:word")
    monkeypatch.setenv("OXYLABS_PROXY_HOST", "pr.oxylabs.io")
    monkeypatch.setenv("OXYLABS_PROXY_PORT", "7777")
    upstream = proxy_config.upstream_proxy_url()
    assert "p@ss:word" not in upstream
    assert "%40" in upstream or "%3A" in upstream
    assert proxy_config.redact_proxy_url(upstream).endswith("@pr.oxylabs.io:7777")


def test_sqlmap_flags_no_proxy_cred(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=True, protocol="http")
    joined = " ".join(result["flags"])
    assert "--proxy-cred" not in joined
    assert result["flags"] == ["--proxy", "http://127.0.0.1:18080"]


def test_hydra_uses_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    result = proxy_config.resolve_for_tool("hydra", use_proxy=True, protocol="http")
    assert result["mode"] == "local_proxy"
    assert result["env"]["HYDRA_PROXY_HTTP"] == "http://127.0.0.1:18080"


def test_unsupported_protocol_for_nikto_socks(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    result = proxy_config.resolve_for_tool("nikto", use_proxy=True, protocol="socks5h")
    assert result["mode"] == "unsupported"
    assert result["note"]
    assert result["flags"] == []


def test_use_proxy_true_without_credentials_is_direct(monkeypatch):
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    result = proxy_config.resolve_for_tool("ffuf", use_proxy=True)
    assert result["mode"] == "unsupported"
    note = (result["note"] or "").lower()
    assert "credential" in note or "not configured" in note


def test_credentials_from_redis_without_env(monkeypatch):
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    proxy_settings.save_settings(
        {
            "username": "redis-user",
            "password": "redis-pass",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        }
    )
    assert proxy_config.credentials_configured() is True
    upstream = proxy_config.upstream_proxy_url()
    assert proxy_config.redact_proxy_url(upstream) == (
        "http://redis-user:***@pr.oxylabs.io:7777"
    )
    result = proxy_config.resolve_for_tool("sqlmap", use_proxy=True)
    assert result["mode"] == "local_proxy"
