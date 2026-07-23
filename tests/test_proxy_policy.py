"""Tests for mission proxy routing policy."""

from tools.proxy_policy import parse_launch_use_proxy, proxy_default_enabled, resolve_use_proxy


def test_no_credentials_means_direct(monkeypatch):
    monkeypatch.delenv("OXYLABS_PROXY_USERNAME", raising=False)
    monkeypatch.delenv("OXYLABS_PROXY_PASSWORD", raising=False)
    assert resolve_use_proxy(requested=True) is False
    assert parse_launch_use_proxy({}) is False


def test_default_on_when_credentials_and_env_default(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "pass")
    monkeypatch.setenv("FIREBREAK_PROXY_DEFAULT", "true")
    assert proxy_default_enabled() is True
    assert resolve_use_proxy() is True
    assert parse_launch_use_proxy({}, evasion="aggressive") is True


def test_explicit_off_honored_without_waf(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "pass")
    assert resolve_use_proxy(requested=False) is False
    assert parse_launch_use_proxy({"use_proxy": False}, evasion="aggressive") is False


def test_waf_forces_proxy_even_when_launch_payload_off(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "pass")
    assert (
        resolve_use_proxy(requested=False, waf_blocked=True, cdn=True) is True
    )


def test_aggressive_evasion_enables_proxy_when_default_on(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "pass")
    monkeypatch.setenv("FIREBREAK_PROXY_DEFAULT", "false")
    assert resolve_use_proxy(evasion="aggressive") is True
