"""Tests for advanced recon methodology catalog."""

from __future__ import annotations

from tools.recon_methodology import FULL_WEB_RECON_TOOLS, phase_by_id, tools_for_phase
from tools.xss_payloads import payloads_for_context


def test_phase_lookup():
    row = phase_by_id("subdomain_enum")
    assert row is not None
    assert "subfinder" in tools_for_phase("subdomain_enum")


def test_full_rotation_has_core_tools():
    assert "katana" in FULL_WEB_RECON_TOOLS
    assert "sqlmap" in FULL_WEB_RECON_TOOLS


def test_xss_payload_catalog():
    rows = payloads_for_context("html")
    assert any("script" in row.lower() for row in rows)
    waf_rows = payloads_for_context("waf")
    assert len(waf_rows) > 0
    assert any("confirm(1)" in row or "alert" in row.lower() for row in waf_rows)
