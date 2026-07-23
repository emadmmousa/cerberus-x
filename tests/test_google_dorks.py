"""Tests for google dork catalog helpers."""

from __future__ import annotations

import pytest

from tools.google_dorks import CORE_DORKS, dorks_for_domain, sample_dorks, substitute_domain


def test_core_dorks_substitute_domain():
    query = substitute_domain(CORE_DORKS[0], "example.com")
    assert "example.com" in query
    assert "TARGET-DOMAIN.COM" not in query


def test_dorks_for_domain_deduplicates():
    rows = dorks_for_domain("example.com", include_catalog=False)
    assert len(rows) == len(set(rows))
    assert all("example.com" in row for row in rows)


def test_sample_dorks_respects_count():
    rows = sample_dorks("example.com", count=3)
    assert len(rows) <= 3


def test_invalid_domain_raises():
    with pytest.raises(ValueError):
        substitute_domain(CORE_DORKS[0], "not a domain")
