"""Unit tests for scanner authorization and vulnerability probes."""

from __future__ import annotations

import json

import pytest

from scanner.authorization import AuthorizationEnforcer
from scanner.vulnerability_scanner import VulnerabilityScanner


class _FakeResp:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class _FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.verify = True
        self.proxies = {}
        self.calls = []

    def get(self, url, params=None, timeout=5, allow_redirects=True):
        self.calls.append(("GET", url, params, allow_redirects))
        return self.responses.pop(0) if self.responses else None

    def post(self, url, params=None, data=None, timeout=5, allow_redirects=True):
        self.calls.append(("POST", url, data, allow_redirects))
        return self.responses.pop(0) if self.responses else None


def test_authz_default_allows(monkeypatch):
    monkeypatch.delenv("CERBERUS_REQUIRE_AUTHZ", raising=False)
    assert AuthorizationEnforcer.check("https://anything.example") is True


def test_authz_enforced_allowlist(tmp_path, monkeypatch):
    path = tmp_path / "authorized_targets.json"
    path.write_text(json.dumps({"targets": ["lab.example"]}), encoding="utf-8")
    monkeypatch.setenv("CERBERUS_REQUIRE_AUTHZ", "true")
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    assert AuthorizationEnforcer.check("https://lab.example/app") is True
    assert AuthorizationEnforcer.check("https://evil.example") is False


def test_scanner_detects_reflected_xss():
    session = _FakeSession(
        [
            _FakeResp(200, "ok", {}),  # waf
            _FakeResp(200, "clean"),  # sqli 1
            _FakeResp(200, "clean"),  # sqli 2
            _FakeResp(200, "hello <script>alert(1)</script>"),  # xss hit
            _FakeResp(200, "nope"),  # path
            _FakeResp(200, "nope", {}),  # redirect
        ]
    )
    scanner = VulnerabilityScanner("https://lab.example", session=session)
    findings = scanner.scan_all()
    types = {f["type"] for f in findings}
    assert "XSS" in types


def test_scanner_open_redirect_respects_allow_redirects_false():
    session = _FakeSession(
        [
            _FakeResp(200, "ok"),  # waf
            _FakeResp(200, "clean"),  # sqli 1
            _FakeResp(200, "clean"),  # sqli 2
            _FakeResp(200, "clean"),  # xss 1
            _FakeResp(200, "clean"),  # xss 2
            _FakeResp(200, "clean"),  # path
            _FakeResp(302, "", {"Location": "https://example.invalid/x"}),  # redirect
        ]
    )
    scanner = VulnerabilityScanner("lab.example", session=session)
    findings = scanner.scan_all()
    assert any(f["type"] == "Open Redirect" for f in findings)
    assert any(call[3] is False for call in session.calls if call[0] == "GET")
