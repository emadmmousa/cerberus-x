"""Chaos helpers — opt-in destructive checks (not run in default CI)."""

from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.environ.get("FIREBREAK_BASE_URL", "http://127.0.0.1:5000")
RUN_CHAOS = os.environ.get("FIREBREAK_RUN_CHAOS", "").lower() in {"1", "true", "yes"}


pytestmark = pytest.mark.skipif(not RUN_CHAOS, reason="set FIREBREAK_RUN_CHAOS=1")


def test_invalid_payload_rejected_or_handled():
    resp = requests.post(
        f"{BASE_URL}/api/run",
        json={"target": ""},
        timeout=10,
    )
    assert resp.status_code in {400, 422}


def test_health_survives_parallel_reads():
    codes = []
    for _ in range(20):
        codes.append(requests.get(f"{BASE_URL}/health", timeout=5).status_code)
    assert all(c == 200 for c in codes)
