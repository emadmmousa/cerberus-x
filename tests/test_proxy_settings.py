import json
import os

import pytest

from tools import proxy_settings


@pytest.fixture(autouse=True)
def _memory_backend(monkeypatch):
    monkeypatch.setenv("FIREBREAK_PROXY_SETTINGS_BACKEND", "memory")
    proxy_settings._memory_clear()
    yield
    proxy_settings._memory_clear()


def test_parse_proxy_url_http():
    parsed = proxy_settings.parse_proxy_url(
        "http://customer-x:s3cret@pr.oxylabs.io:7777"
    )
    assert parsed == {
        "username": "customer-x",
        "password": "s3cret",
        "host": "pr.oxylabs.io",
        "port": 7777,
        "protocol": "http",
    }


def test_parse_proxy_url_socks5h():
    parsed = proxy_settings.parse_proxy_url(
        "socks5h://u:p@pr.oxylabs.io:7777"
    )
    assert parsed["protocol"] == "socks5h"
    assert parsed["username"] == "u"


def test_parse_proxy_url_rejects_missing_user():
    with pytest.raises(ValueError, match="username"):
        proxy_settings.parse_proxy_url("http://pr.oxylabs.io:7777")


def test_merge_put_body_url_and_fields_fields_win():
    body = {
        "proxy_url": "http://urluser:urlpass@host.example:7777",
        "username": "fielduser",
        "password": "fieldpass",
        "host": "field.host",
        "port": 8888,
        "protocol": "https",
    }
    merged = proxy_settings.merge_put_body(body, existing=None)
    assert merged["username"] == "fielduser"
    assert merged["password"] == "fieldpass"
    assert merged["host"] == "field.host"
    assert merged["port"] == 8888
    assert merged["protocol"] == "https"


def test_merge_put_body_empty_password_keeps_existing():
    existing = {
        "username": "u",
        "password": "keep-me",
        "host": "pr.oxylabs.io",
        "port": 7777,
        "protocol": "http",
    }
    merged = proxy_settings.merge_put_body(
        {
            "username": "u2",
            "password": "",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        },
        existing=existing,
    )
    assert merged["password"] == "keep-me"
    assert merged["username"] == "customer-u2"


def test_normalize_rejects_dashboard_email():
    with pytest.raises(ValueError, match="dashboard login email"):
        proxy_settings.normalize_oxylabs_username("ceo@wksagency.com", "pr.oxylabs.io")


def test_normalize_adds_customer_prefix():
    assert (
        proxy_settings.normalize_oxylabs_username("emadmousa_AJjFI", "pr.oxylabs.io")
        == "customer-emadmousa_AJjFI"
    )


def test_normalize_adds_user_prefix_for_datacenter():
    assert (
        proxy_settings.normalize_oxylabs_username("scanner", "dc.oxylabs.io")
        == "user-scanner"
    )


def test_merge_put_body_rejects_email_username():
    with pytest.raises(ValueError, match="dashboard login email"):
        proxy_settings.merge_put_body(
            {
                "username": "ceo@wksagency.com",
                "password": "secret",
                "host": "pr.oxylabs.io",
                "port": 7777,
                "protocol": "http",
            },
            existing=None,
        )


def test_public_view_never_includes_password():
    view = proxy_settings.public_view(
        {
            "username": "customer-x",
            "password": "s3cret",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        },
        source="redis",
    )
    assert view["password_set"] is True
    assert "password" not in view
    assert "s3cret" not in json.dumps(view)
    assert view["proxy_url_redacted"].endswith("@pr.oxylabs.io:7777")
    assert "***" in view["proxy_url_redacted"]


def test_save_and_load_settings():
    data = {
        "username": "u",
        "password": "p",
        "host": "pr.oxylabs.io",
        "port": 7777,
        "protocol": "http",
    }
    proxy_settings.save_settings(data)
    assert proxy_settings.load_settings() == data


def test_clear_settings():
    proxy_settings.save_settings(
        {
            "username": "u",
            "password": "p",
            "host": "h",
            "port": 1,
            "protocol": "http",
        }
    )
    proxy_settings.clear_settings()
    assert proxy_settings.load_settings() is None


def test_load_credentials_prefers_redis_over_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "env-user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "env-pass")
    monkeypatch.setenv("OXYLABS_PROXY_HOST", "env.host")
    monkeypatch.setenv("OXYLABS_PROXY_PORT", "9999")
    proxy_settings.save_settings(
        {
            "username": "redis-user",
            "password": "redis-pass",
            "host": "redis.host",
            "port": 7777,
            "protocol": "http",
        }
    )
    creds = proxy_settings.load_credentials()
    assert creds is not None
    assert creds["username"] == "redis-user"
    assert creds["password"] == "redis-pass"
    assert creds["host"] == "redis.host"


def test_load_credentials_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "env-user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "env-pass")
    monkeypatch.setenv("OXYLABS_PROXY_HOST", "pr.oxylabs.io")
    monkeypatch.setenv("OXYLABS_PROXY_PORT", "7777")
    monkeypatch.setenv("OXYLABS_PROXY_PROTOCOL", "http")
    creds = proxy_settings.load_credentials()
    assert creds is not None
    assert creds["username"] == "env-user"
    assert creds["source"] == "env"
