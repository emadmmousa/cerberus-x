"""Recon catalog API tests."""

from __future__ import annotations


def _client():
    from orchestrator import dashboard

    return dashboard.app.test_client()


def test_recon_methodology_endpoint():
    client = _client()
    resp = client.get("/api/recon/methodology")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["phases"]) >= 10
    assert any(row["id"] == "subdomain_enum" for row in data["phases"])
    assert data["specialist_playbooks"]


def test_recon_dorks_requires_domain():
    client = _client()
    resp = client.get("/api/recon/dorks")
    assert resp.status_code == 400


def test_recon_dorks_substitutes_domain():
    client = _client()
    resp = client.get("/api/recon/dorks?domain=example.com&limit=5&catalog=0")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["domain"] == "example.com"
    assert data["count"] >= 1
    assert all("example.com" in row for row in data["dorks"])


def test_recon_xss_payloads():
    client = _client()
    resp = client.get("/api/recon/xss-payloads?context=waf")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] > 0
    assert data["context"] == "waf"
