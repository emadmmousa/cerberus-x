"""Unit tests for security, dynamic playbooks, and AI decision helpers."""

from __future__ import annotations

import json

import pytest

from orchestrator.ai_decision import AIDecisionEngine
from orchestrator.dynamic_playbook import DynamicPlaybookCompiler
from security.audit import audit_log, recent_audit
from security.auth import AuthManager
from security.waf import WAFMiddleware
from security.vault_integration import VaultClient
from utils.threat_intel import ThreatIntelFetcher
from workers.scaling import DynamicScaler


def test_threat_intel_hints():
    hits = ThreatIntelFetcher().fetch_for_services(["http", "ssh", "unknown"])
    assert "http" in hits
    assert "ssh" in hits
    assert "unknown" not in hits


def test_waf_patterns_detect_sqli():
    assert WAFMiddleware.PATTERNS["sqli"].search("SELECT * FROM users")
    assert WAFMiddleware.PATTERNS["xss"].search("<script>alert(1)</script>")


def test_vault_client_soft_fail(monkeypatch):
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    VaultClient._instance = None
    client = VaultClient()
    assert client.available is False
    assert client.get_secret("x") is None


def test_audit_log_records(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    # Force memory redis by clearing singleton
    import utils.redis_utils as ru

    ru._client = None
    entry = audit_log("UNIT_TEST", {"ok": True}, severity="info")
    assert entry["event_type"] == "UNIT_TEST"
    recent = recent_audit(5)
    assert any(r.get("event_type") == "UNIT_TEST" for r in recent)


def test_auth_honeypot_accounts():
    assert "admin_honeypot" in AuthManager.HONEYPOT_ACCOUNTS


def test_dynamic_condition_true():
    ok = DynamicPlaybookCompiler._eval_condition(
        "{{context.allow_scan}}",
        {},
        {"allow_scan": True},
    )
    assert ok is True


def test_dynamic_condition_compare():
    ok = DynamicPlaybookCompiler._eval_condition(
        "{{context.aggressive_level}} > 3",
        {},
        {"aggressive_level": 5},
    )
    assert ok is True
    no = DynamicPlaybookCompiler._eval_condition(
        "{{context.aggressive_level}} > 3",
        {},
        {"aggressive_level": 1},
    )
    assert no is False


def test_dynamic_compile_without_ai():
    yaml_text = """
steps:
  - tool: nmap
    params:
      target: "{{context.target}}"
      ports: "80,443"
    when: "{{context.allow_scan}}"
  - tool: nuclei
    params:
      target: "{{context.target}}"
    when: "{{context.aggressive_level}} > 9"
"""
    tasks = DynamicPlaybookCompiler.compile(
        yaml_text,
        "sess-1",
        {"target": "https://example.com", "allow_scan": True, "aggressive_level": 2},
        use_ai=False,
    )
    assert len(tasks) == 1
    assert tasks[0]["tool"] == "nmap"
    assert tasks[0]["params"]["target"] == "https://example.com"


def test_ai_decision_fallback(monkeypatch):
    engine = AIDecisionEngine()
    monkeypatch.setattr(engine, "_ollama_generate", lambda prompt: "not-json")
    plan = engine.decide(
        "s1",
        {
            "target": "https://example.com",
            "ports": [{"port": "443", "service": "https"}],
        },
    )
    assert plan
    assert all("tool" in p for p in plan)


def test_ai_decision_parse_list():
    engine = AIDecisionEngine()
    plan = engine._parse_plan('[["nmap", {"ports": "80"}], ["whatweb", {}]]')
    assert plan[0]["tool"] == "nmap"
    assert plan[1]["tool"] == "whatweb"


def test_scaler_shard_nmap():
    shards = DynamicScaler.shard_nmap("example.com", "1-100", "sid")
    assert len(shards) >= 2
    assert shards[0]["tool"] == "nmap"


def test_scaler_noop_without_k8s(monkeypatch):
    import utils.redis_utils as ru

    ru._client = None
    scaler = DynamicScaler()
    scaler.k8s_api = None
    result = scaler.scale_workers()
    assert result["scaled"] is False
    assert "target_replicas" in result
