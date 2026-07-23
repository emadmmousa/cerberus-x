"""Tests for the cyber scaffold marketplace catalog."""

from orchestrator.ai.marketplace import builtin_catalog, marketplace_status
from orchestrator.ai.scaffold_catalog import SCAFFOLD_CATEGORIES, catalog_categories


def test_builtin_catalog_has_cyber_domains():
    catalog = builtin_catalog()
    assert len(catalog) >= 80
    ids = [row["id"] for row in catalog]
    assert len(ids) == len(set(ids)), "duplicate scaffold ids"
    assert "sql-injection" in ids
    assert "kubernetes-security" in ids


def test_catalog_categories_cover_entries():
    catalog = builtin_catalog()
    categories = catalog_categories(catalog)
    assert categories
    assert sum(c["count"] for c in categories) == len(catalog)
    assert categories[0]["id"] == "Core platform"


def test_marketplace_status_includes_categories():
    status = marketplace_status()
    assert "categories" in status
    assert status["count"] >= len(status["catalog"])
    assert len(status["catalog"]) >= 80


def test_scaffold_entries_have_required_fields():
    for row in builtin_catalog():
        assert row.get("id")
        assert row.get("label")
        assert row.get("model")
        assert row.get("base_url_hint")
        assert row.get("tasks")
        assert row.get("category")
