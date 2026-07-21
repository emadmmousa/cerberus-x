"""Tests for Redis Blackboard (uses fakeredis if available, else skip)."""

import json

import pytest

pytest.importorskip("redis")

from orchestrator.ai import blackboard


class _FakeRedis:
    def __init__(self):
        self.store = {}
        self.published = []

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    def delete(self, key):
        return 1 if self.store.pop(key, None) is not None else 0

    def scan_iter(self, match=None, count=200):
        prefix = match.rstrip("*") if match else ""
        for k in list(self.store.keys()):
            if k.startswith(prefix):
                yield k

    def publish(self, channel, message):
        self.published.append((channel, message))
        return 1


@pytest.fixture
def fake_bb(monkeypatch):
    client = _FakeRedis()
    monkeypatch.setattr(blackboard, "_client", lambda: client)
    return client


def test_put_get_roundtrip(fake_bb):
    out = blackboard.put("m1", "findings.ports", {"ports": ["80", "443"]})
    assert out["ok"] is True
    assert out["version"] == 1
    doc = blackboard.get("m1", "findings.ports")
    assert doc["value"]["ports"] == ["80", "443"]
    assert doc["version"] == 1


def test_cas_conflict(fake_bb):
    blackboard.put("m1", "hyp", "a")
    bad = blackboard.put("m1", "hyp", "b", expected_version=99)
    assert bad["ok"] is False
    assert bad["conflict"] is True
    ok = blackboard.put("m1", "hyp", "b", expected_version=1)
    assert ok["ok"] is True
    assert ok["version"] == 2


def test_list_keys(fake_bb):
    blackboard.put("m1", "a", 1)
    blackboard.put("m1", "b", 2)
    blackboard.put("m2", "a", 3)
    assert blackboard.list_keys("m1") == ["a", "b"]


def test_org_isolation(fake_bb, monkeypatch):
    monkeypatch.setenv("FIREBREAK_DEFAULT_ORG", "default")
    blackboard.put("m1", "a", 1, org_id="org-a")
    blackboard.put("m1", "a", 2, org_id="org-b")
    assert blackboard.get("m1", "a", org_id="org-a")["value"] == 1
    assert blackboard.get("m1", "a", org_id="org-b")["value"] == 2
    assert blackboard.list_keys("m1", org_id="org-a") == ["a"]


def test_consensus_key_shape(fake_bb):
    blackboard.put(
        "m-cons",
        "consensus",
        {
            "step": 1,
            "confidence": 0.8,
            "mode": "pick_best",
            "sources": ["ollama-primary", "ollama-fallback"],
        },
    )
    doc = blackboard.get("m-cons", "consensus")
    assert doc["value"]["confidence"] == 0.8
    assert doc["value"]["mode"] == "pick_best"
