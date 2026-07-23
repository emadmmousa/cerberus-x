"""Breach intelligence integration tests."""

from __future__ import annotations

import json


def test_provider_status_without_keys(monkeypatch):
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    monkeypatch.delenv("FIREBREAK_DEHASHED_API_KEY", raising=False)
    monkeypatch.delenv("LEAKCHECK_API_KEY", raising=False)
    monkeypatch.delenv("FIREBREAK_LEAKCHECK_API_KEY", raising=False)
    from orchestrator.osint.breach_providers import provider_status

    status = provider_status()
    assert status["enabled"] is True
    assert status["dehashed"]["configured"] is False
    assert status["leakcheck"]["configured"] is False
    assert status["ready"] is False


def test_redact_breach_record_strips_passwords():
    from orchestrator.osint.breach_providers import redact_breach_record

    row = redact_breach_record(
        {
            "email": ["user@example.com"],
            "password": ["secret123"],
            "database_name": "Example DB",
        }
    )
    assert "password" not in row
    assert row["password_present"] is True
    assert row["password_count"] == 1
    assert row["email"] == ["user@example.com"]


def test_build_dehashed_query_for_kinds():
    from orchestrator.osint.breach_providers import build_dehashed_query, leakcheck_query_type

    assert build_dehashed_query("email", "a@b.com") == "a@b.com"
    assert build_dehashed_query("username", "alice") == 'username:"alice"'
    assert build_dehashed_query("domain", "example.com") == 'email:"@example.com"'
    assert leakcheck_query_type("mobile") == "phone"
    assert leakcheck_query_type("full_name") == "keyword"


def test_lookup_seeds_mocked(monkeypatch):
    from orchestrator.osint import breach_service as svc

    monkeypatch.setenv("DEHASHED_API_KEY", "test-dehashed")
    monkeypatch.setenv("LEAKCHECK_API_KEY", "test-leakcheck")

    def fake_dehashed(query, **kwargs):
        return {
            "provider": "dehashed",
            "query": query,
            "total": 1,
            "entries": [{"email": ["a@b.com"], "password_present": True, "database_name": "DB"}],
            "productive": True,
        }

    def fake_leakcheck(query, **kwargs):
        return {
            "provider": "leakcheck",
            "query": query,
            "found": 1,
            "entries": [{"email": "a@b.com", "source": {"name": "BreachedSite"}}],
            "productive": True,
        }

    monkeypatch.setattr(svc, "dehashed_search", fake_dehashed)
    monkeypatch.setattr(svc, "leakcheck_lookup", fake_leakcheck)

    result = svc.lookup_seeds([{"kind": "email", "value": "a@b.com", "display": "a@b.com"}])
    assert result["productive"] is True
    assert result["summary"]["seeds_with_hits"] == 1
    assert result["results"][0]["total_hits"] == 2
    entry = result["results"][0]["breach_vault"]["entries"][0]
    assert "password" not in entry
    assert entry["password_present"] is True
    assert "dehashed" not in result["providers"]
    assert result["providers"]["breach_vault"]["product"] == "Breach Vault"


def test_lookup_filters_non_matching_breach_records(monkeypatch):
    from orchestrator.osint import breach_service as svc

    monkeypatch.setenv("DEHASHED_API_KEY", "test-dehashed")
    monkeypatch.setenv("LEAKCHECK_API_KEY", "test-leakcheck")

    def fake_dehashed(query, **kwargs):
        return {
            "provider": "dehashed",
            "query": query,
            "total": 2,
            "entries": [
                {"email": ["a@b.com"], "database_name": "Match"},
                {"email": ["other@c.com"], "database_name": "Noise"},
            ],
            "productive": True,
        }

    def fake_leakcheck(query, **kwargs):
        return {
            "provider": "leakcheck",
            "query": query,
            "found": 2,
            "entries": [
                {"email": "a@b.com", "source": {"name": "Match"}},
                {"email": "other@c.com", "source": {"name": "Noise"}},
            ],
            "productive": True,
        }

    monkeypatch.setattr(svc, "dehashed_search", fake_dehashed)
    monkeypatch.setattr(svc, "leakcheck_lookup", fake_leakcheck)

    row = svc.lookup_seed({"kind": "email", "value": "a@b.com", "display": "a@b.com"})
    assert len(row["dehashed"]["entries"]) == 1
    assert len(row["leakcheck"]["entries"]) == 1
    assert row["total_hits"] == 2


def test_social_url_uses_handle_for_providers(monkeypatch):
    from orchestrator.osint import breach_service as svc

    monkeypatch.setenv("DEHASHED_API_KEY", "test-dehashed")
    monkeypatch.setenv("LEAKCHECK_API_KEY", "test-leakcheck")
    captured: dict[str, str] = {}

    def fake_dehashed(query, **kwargs):
        captured["dehashed"] = query
        return {"provider": "dehashed", "total": 0, "entries": [], "productive": False}

    def fake_leakcheck(query, **kwargs):
        captured["leakcheck_query"] = query
        captured["leakcheck_type"] = kwargs.get("query_type")
        return {"provider": "leakcheck", "found": 0, "entries": [], "productive": False}

    monkeypatch.setattr(svc, "dehashed_search", fake_dehashed)
    monkeypatch.setattr(svc, "leakcheck_lookup", fake_leakcheck)

    svc.lookup_seed(
        {
            "kind": "social_url",
            "value": "https://instagram.com/alice",
            "display": "https://instagram.com/alice",
        }
    )
    assert captured["dehashed"] == 'username:"alice"'
    assert captured["leakcheck_query"] == "alice"
    assert captured["leakcheck_type"] == "keyword"


def test_inject_osint_seeds_into_tools():
    from tools.breach_intel import inject_osint_seeds_into_tools, with_osint_seeds_args

    seeds = [{"kind": "email", "value": "a@b.com"}]
    args = with_osint_seeds_args(["--limit", "10"], seeds)
    assert "--seeds" in args
    assert json.loads(args[args.index("--seeds") + 1])[0]["value"] == "a@b.com"

    tools = inject_osint_seeds_into_tools(
        [{"tool": "nmap", "args": []}, {"tool": "breach_intel", "args": ["--limit", "5"]}],
        seeds,
    )
    assert " --seeds " not in str(tools[0]["args"])
    assert "--seeds" in tools[1]["args"]


def test_breach_intel_wrapper_registered():
    from orchestrator.tasks import _TASK_MAP
    from tools.inventory import catalog_by_name

    assert "breach_intel" in _TASK_MAP
    assert "katana" in _TASK_MAP
    assert "breach_intel" in catalog_by_name()
    assert "katana" in catalog_by_name()


def test_attack_methods_include_breach_intel():
    from tools.attack_methods import FULL_TOOL_ROTATION, list_methods

    assert "breach_intel" in FULL_TOOL_ROTATION
    ids = {m["id"] for m in list_methods(posture="aggressive")}
    assert "breach_intel_lookup" in ids


def test_seeds_from_target_and_args():
    from tools.breach_intel import scan

    result = scan(
        "user@example.com",
        ["--seeds", '[{"kind":"email","value":"user@example.com"}]'],
    )
    assert result["tool"] == "breach_intel"
    assert result.get("skipped") or result.get("seeds")


def test_breach_status_api(monkeypatch):
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    monkeypatch.delenv("LEAKCHECK_API_KEY", raising=False)
    from orchestrator import dashboard

    client = dashboard.app.test_client()
    resp = client.get("/api/osint/breach/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["enabled"] is True
    assert data["ready"] is False
    assert "breach_vault" in data
    assert "leak_radar" in data
    assert "dehashed" not in data


def test_breach_lookup_api_mocked(monkeypatch):
    from orchestrator import dashboard

    monkeypatch.setenv("DEHASHED_API_KEY", "test")
    monkeypatch.setenv("LEAKCHECK_API_KEY", "test")
    monkeypatch.setattr(
        "orchestrator.api.osint_breach.lookup_seeds",
        lambda seeds, **kwargs: {
            "productive": True,
            "seeds": seeds,
            "summary": {"seed_count": len(seeds), "total_hits": 1},
        },
    )

    client = dashboard.app.test_client()
    resp = client.post(
        "/api/osint/breach/lookup",
        json={"seeds": [{"kind": "email", "value": "user@example.com"}]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["productive"] is True
