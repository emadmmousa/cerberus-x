"""Lightweight integration smoke tests (skip if stack is down)."""

from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("CERBERUS_BASE_URL", "http://127.0.0.1:5000")


def _alive() -> bool:
    try:
        return requests.get(f"{BASE_URL}/health", timeout=2).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _alive(), reason="orchestrator not reachable")


def test_health():
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_auth_status_unauthenticated():
    resp = requests.get(f"{BASE_URL}/auth/status", timeout=5)
    assert resp.status_code == 200
    assert resp.json().get("authenticated") is False


def test_aggressive_decide():
    resp = requests.post(
        f"{BASE_URL}/api/aggressive/decide",
        json={
            "session_id": "integration-sess",
            "results": {
                "target": "https://example.com",
                "ports": [{"port": "443", "service": "https"}],
            },
        },
        timeout=60,
    )
    assert resp.status_code == 200
    assert "plan" in resp.json()
