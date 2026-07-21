"""Cost-route ordering for multi-scaffold router."""

from orchestrator.ai.scaffold_client import OpenAICompatibleScaffold, ScaffoldSpec
from orchestrator.ai import router


def test_cost_estimate_nonzero():
    client = OpenAICompatibleScaffold(
        ScaffoldSpec(
            id="paid",
            model="x",
            base_url="http://x",
            cost_per_1k=0.002,
        )
    )
    assert client.cost_estimate(500, 500) == 0.002
    assert client.cost_estimate() > 0


def test_order_clients_cheaper_first(monkeypatch):
    monkeypatch.setenv("FIREBREAK_SCAFFOLD_COST_ROUTE", "true")
    cheap = OpenAICompatibleScaffold(
        ScaffoldSpec(id="local", model="a", base_url="http://a", cost_per_1k=0.0)
    )
    paid = OpenAICompatibleScaffold(
        ScaffoldSpec(id="paid", model="b", base_url="http://b", cost_per_1k=0.01)
    )
    monkeypatch.setattr(router, "latency_ema", lambda _sid: None)
    ordered = router._order_clients([paid, cheap])
    assert [c.spec.id for c in ordered] == ["local", "paid"]


def test_complete_for_plan_cost_meta(monkeypatch):
    monkeypatch.setenv("FIREBREAK_MULTI_SCAFFOLD", "true")
    monkeypatch.setenv("FIREBREAK_SCAFFOLD_COST_ROUTE", "true")

    cheap = OpenAICompatibleScaffold(
        ScaffoldSpec(id="local", model="a", base_url="http://a", cost_per_1k=0.0)
    )
    paid = OpenAICompatibleScaffold(
        ScaffoldSpec(id="paid", model="b", base_url="http://b", cost_per_1k=0.01)
    )
    cheap.complete = lambda messages, temperature=0.3: '{"phase_name":"x","reason":"r","parallel":false,"stop":true,"tools":[]}'  # type: ignore
    paid.complete = lambda messages, temperature=0.3: None  # type: ignore

    monkeypatch.setattr(router, "build_enabled_clients", lambda: [paid, cheap])
    monkeypatch.setattr(router, "build_primary_scaffold", lambda: cheap)
    monkeypatch.setattr(router, "latency_ema", lambda _sid: None)

    text, meta = router.complete_for_plan([{"role": "user", "content": "hi"}])
    assert text
    assert meta["mode"] == "multi"
    assert meta["cost_route"] is True
    assert "cost_usd" in meta
    assert meta["chosen_scaffold"] == "local"
