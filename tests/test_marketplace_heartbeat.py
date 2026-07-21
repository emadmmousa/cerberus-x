"""Wave 5 marketplace + control-plane heartbeat tests."""

from orchestrator.ai.marketplace import marketplace_status, register_scaffold, builtin_catalog
from orchestrator.ai.control_plane import heartbeat_payload, send_heartbeat


def test_builtin_catalog_nonempty():
    assert len(builtin_catalog()) >= 2


def test_marketplace_community_cannot_register(monkeypatch):
    monkeypatch.delenv("FIREBREAK_EDITION", raising=False)
    status = marketplace_status()
    assert status["can_register"] is False
    assert status["count"] >= 2


def test_marketplace_pro_can_register(monkeypatch):
    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    monkeypatch.setattr(
        "orchestrator.ai.marketplace.list_registered",
        lambda: [],
    )
    monkeypatch.setattr(
        "orchestrator.ai.marketplace._redis",
        lambda: None,
    )
    row = register_scaffold(
        {
            "id": "custom-1",
            "model": "my-model",
            "label": "Custom",
            "base_url": "http://localhost:9999/v1",
            "cost_per_1k": 0.001,
        }
    )
    assert row["id"] == "custom-1"
    assert row["source"] == "registered"
    assert row["base_url"] == "http://localhost:9999/v1"


def test_unregister_scaffold(monkeypatch):
    from orchestrator.ai.marketplace import unregister_scaffold

    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    store = {
        "rows": [
            {
                "id": "custom-1",
                "model": "m",
                "base_url": "http://x",
                "source": "registered",
            }
        ]
    }

    class Fake:
        def get(self, key):
            import json

            return json.dumps(store["rows"])

        def set(self, key, value, ex=None):
            import json

            store["rows"] = json.loads(value)
            return True

    monkeypatch.setattr("orchestrator.ai.marketplace._redis", lambda: Fake())
    assert unregister_scaffold("custom-1") is True
    assert store["rows"] == []
    assert unregister_scaffold("missing") is False


def test_marketplace_delete_endpoint(monkeypatch):
    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    monkeypatch.setattr(
        "orchestrator.ai.marketplace.unregister_scaffold",
        lambda sid: sid == "custom-1",
    )
    from orchestrator import dashboard

    client = dashboard.app.test_client()
    resp = client.delete("/api/scaffolds/marketplace/custom-1")
    assert resp.status_code == 200
    assert resp.get_json()["removed"] == "custom-1"
    missing = client.delete("/api/scaffolds/marketplace/nope")
    assert missing.status_code == 404



def test_registered_scaffold_appears_in_list_enabled(monkeypatch):
    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("FIREBREAK_LLM_MODEL", "firebreak")
    monkeypatch.setenv("FIREBREAK_LLM_FALLBACK_MODEL", "qwen2.5:7b")
    stored = [
        {
            "id": "paid-remote",
            "model": "gpt-4o-mini",
            "base_url": "https://api.example/v1",
            "cost_per_1k": 0.01,
            "enabled": True,
            "source": "registered",
        }
    ]
    monkeypatch.setattr(
        "orchestrator.ai.marketplace.list_registered",
        lambda: stored,
    )
    from orchestrator.ai import scaffolds

    ids = {r["id"] for r in scaffolds.default_scaffolds()}
    assert "paid-remote" in ids
    assert "ollama-primary" in ids


def test_marketplace_endpoint(monkeypatch):
    monkeypatch.delenv("FIREBREAK_EDITION", raising=False)
    from orchestrator import dashboard

    client = dashboard.app.test_client()
    resp = client.get("/api/scaffolds/marketplace")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 2
    assert "catalog" in data


def test_marketplace_register_forbidden_community(monkeypatch):
    monkeypatch.delenv("FIREBREAK_EDITION", raising=False)
    from orchestrator import dashboard

    client = dashboard.app.test_client()
    resp = client.post(
        "/api/scaffolds/marketplace",
        json={"id": "x", "model": "y"},
    )
    assert resp.status_code == 403


def test_heartbeat_skipped_without_managed(monkeypatch):
    monkeypatch.delenv("FIREBREAK_EDITION", raising=False)
    monkeypatch.delenv("FIREBREAK_MANAGED_HOSTING", raising=False)
    result = send_heartbeat()
    assert result["skipped"] is True
    assert "payload" in result


def test_heartbeat_endpoint_get(monkeypatch):
    monkeypatch.setenv("FIREBREAK_EDITION", "pro")
    monkeypatch.setenv("FIREBREAK_MANAGED_HOSTING", "true")
    monkeypatch.setenv("FIREBREAK_CONTROL_PLANE_URL", "https://control.example")
    from orchestrator import dashboard

    client = dashboard.app.test_client()
    resp = client.get("/api/edition/heartbeat")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["payload"]["managed_hosting_enabled"] is True
    assert data["payload"]["control_plane_url"] == "https://control.example"


def test_heartbeat_payload_shape():
    payload = heartbeat_payload()
    assert "ts" in payload
    assert "edition" in payload
    assert "features" in payload
