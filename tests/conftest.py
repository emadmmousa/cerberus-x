import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
src_path = str(SRC)
if src_path not in sys.path:
    sys.path.insert(0, src_path)


@pytest.fixture(autouse=True)
def _disable_worker_preflight_in_unit_tests(request, monkeypatch):
    """Unit tests have no Celery workers; keep preflight enabled only where tested."""
    if request.node.name in {
        "test_assert_full_arsenal_ready_raises",
        "test_assert_workers_ready_raises",
    }:
        return
    monkeypatch.setenv("FIREBREAK_WORKER_PREFLIGHT", "false")
