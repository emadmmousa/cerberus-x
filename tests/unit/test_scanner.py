"""Unit tests for scanner authorization and vulnerability probes."""

from __future__ import annotations

import json

from scanner.authorization import AuthorizationEnforcer
from scanner.vulnerability_scanner import VulnerabilityScanner


class _FakeResp:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class _FakeSession:
    """URL-aware fake: enough responses for expanded SQLi/NoSQL probe loops."""

    def __init__(self, overrides=None):
        self.overrides = list(overrides or [])
        self.headers = {}
        self.verify = True
        self.proxies = {}
        self.cookies = {}
        self.calls = []

    def _next(self, method, url, allow_redirects=True, **_kwargs):
        self.calls.append((method, url, _kwargs.get("params"), allow_redirects))
        if self.overrides:
            return self.overrides.pop(0)
        if "/redirect" in url and allow_redirects is False:
            return _FakeResp(302, "", {"Location": "https://example.invalid/x"})
        params = _kwargs.get("params") or {}
        if "input" in params and "<script>" in str(params.get("input", "")):
            return _FakeResp(200, f"hello {params['input']}")
        return _FakeResp(200, "clean")

    def get(self, url, params=None, timeout=5, allow_redirects=True, **kwargs):
        return self._next(
            "GET", url, allow_redirects=allow_redirects, params=params, **kwargs
        )

    def post(
        self,
        url,
        params=None,
        data=None,
        json=None,
        timeout=5,
        allow_redirects=True,
        headers=None,
        **kwargs,
    ):
        return self._next(
            "POST",
            url,
            allow_redirects=allow_redirects,
            params=params,
            data=data,
            json=json,
            headers=headers,
            **kwargs,
        )


def test_authz_default_allows(monkeypatch):
    monkeypatch.delenv("FIREBREAK_REQUIRE_AUTHZ", raising=False)
    assert AuthorizationEnforcer.check("https://anything.example") is True


def test_authz_enforced_allowlist(tmp_path, monkeypatch):
    path = tmp_path / "authorized_targets.json"
    path.write_text(json.dumps({"targets": ["lab.example"]}), encoding="utf-8")
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    assert AuthorizationEnforcer.check("https://lab.example/app") is True
    assert AuthorizationEnforcer.check("https://evil.example") is False


def test_scanner_detects_reflected_xss():
    session = _FakeSession()
    scanner = VulnerabilityScanner(
        "https://lab.example",
        session=session,
        evasion={"random_headers": False, "obfuscate_payloads": False},
    )
    findings = scanner.scan_all()
    types = {f["type"] for f in findings}
    assert "XSS" in types


def test_scanner_open_redirect_respects_allow_redirects_false():
    session = _FakeSession()
    scanner = VulnerabilityScanner(
        "lab.example",
        session=session,
        evasion={"random_headers": False, "obfuscate_payloads": False},
    )
    findings = scanner.scan_all()
    assert any(f["type"] == "Open Redirect" for f in findings)
    assert any(call[3] is False for call in session.calls if call[0] == "GET")
