"""Firebreak dashboard API smoke tests."""

from orchestrator import dashboard


def test_firebreak_status():
    client = dashboard.app.test_client()
    resp = client.get("/api/ai-lab/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["waves"]["w1_blackboard"] is True
    assert "model" in data
    assert "cost_route" in data
    assert isinstance(data["cost_route"], bool)


def test_firebreak_status_cost_route_on(monkeypatch):
    monkeypatch.setenv("FIREBREAK_SCAFFOLD_COST_ROUTE", "true")
    client = dashboard.app.test_client()
    data = client.get("/api/ai-lab/status").get_json()
    assert data["cost_route"] is True


def test_scaffolds_endpoint(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("FIREBREAK_LLM_MODEL", "firebreak")
    client = dashboard.app.test_client()
    resp = client.get("/api/scaffolds")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "scaffolds" in data


def test_rbac_me():
    client = dashboard.app.test_client()
    resp = client.get("/api/rbac/me")
    assert resp.status_code == 200
    assert "role" in resp.get_json()


def test_blackboard_put_get(monkeypatch):
    store = {}

    class Fake:
        def get(self, key):
            return store.get(key)

        def set(self, key, value, ex=None):
            store[key] = value

        def delete(self, key):
            return 1 if store.pop(key, None) is not None else 0

        def scan_iter(self, match=None, count=200):
            prefix = match.rstrip("*") if match else ""
            for k in list(store):
                if k.startswith(prefix):
                    yield k

        def publish(self, *a, **k):
            return 1

    monkeypatch.setattr("orchestrator.ai.blackboard._client", lambda: Fake())
    client = dashboard.app.test_client()
    put = client.put(
        "/api/blackboard/job1/findings",
        json={"value": {"ports": ["443"]}},
    )
    assert put.status_code == 200
    got = client.get("/api/blackboard/job1/findings")
    assert got.status_code == 200
    assert got.get_json()["value"]["ports"] == ["443"]
