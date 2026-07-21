"""Tests for job store, edition, OIDC status, dataset contribute."""

from orchestrator.job_store import PlaybookJobStore
from security.edition import edition, feature_flags, is_pro
from security.oidc import oidc_configured, oidc_status
from orchestrator.dataset.pipeline import (
    accept_contribution,
    synthetic_lab_missions,
)
from orchestrator import dashboard


def test_job_store_roundtrip(monkeypatch):
    store_data = {}

    class Fake:
        def setex(self, key, ttl, value):
            store_data[key] = value

        def get(self, key):
            return store_data.get(key)

        def delete(self, key):
            return 1 if store_data.pop(key, None) is not None else 0

    monkeypatch.setattr("orchestrator.job_store._redis", lambda: Fake())
    jobs = PlaybookJobStore()
    jobs["j1"] = {"state": "PENDING", "phases": []}
    jobs["j1"]["state"] = "STARTED"
    jobs["j1"]["phases"].append({"phase": "recon"})
    jobs.persist("j1")
    # Simulate other replica: empty local, load from redis
    other = PlaybookJobStore()
    assert other["j1"]["state"] == "STARTED"
    assert other["j1"]["phases"][0]["phase"] == "recon"


def test_edition_community_default(monkeypatch):
    monkeypatch.delenv("FIREBREAK_EDITION", raising=False)
    assert edition() == "community"
    assert is_pro() is False
    flags = feature_flags()
    assert flags["arsenal_wrappers"] is True
    assert flags["sso_packaging"] is False


def test_edition_pro(monkeypatch):
    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    assert is_pro() is True
    assert feature_flags()["sso_packaging"] is True


def test_oidc_not_configured(monkeypatch):
    monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)
    monkeypatch.delenv("OIDC_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    assert oidc_configured() is False
    assert oidc_status()["configured"] is False


def test_accept_contribution():
    rec = accept_contribution(
        {"prompt": "What is nmap?", "response": "Port scanner", "license": "CC-BY-4.0"}
    )
    assert rec["id"]
    assert rec["source"] == "community"


def test_synthetic_lab_missions():
    rows = synthetic_lab_missions(targets=["https://lab.example"])
    assert len(rows) == 3


def test_dataset_contribute_api():
    client = dashboard.app.test_client()
    resp = client.post(
        "/api/dataset/contribute",
        json={"prompt": "tool?", "response": "wrapper"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["accepted"] is True


def test_firebreak_status_has_w5():
    client = dashboard.app.test_client()
    data = client.get("/api/ai-lab/status").get_json()
    assert data["waves"]["w5_open_core"] is True
    assert "edition" in data


def test_oidc_api():
    client = dashboard.app.test_client()
    resp = client.get("/api/oidc/status")
    assert resp.status_code == 200
    assert "configured" in resp.get_json()
