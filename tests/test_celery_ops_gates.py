import pytest


@pytest.fixture(autouse=True)
def _clean_admin_store(monkeypatch):
    from utils.redis_utils import get_redis
    from security import admin_store

    r = get_redis()
    try:
        r.delete(admin_store.SETTINGS_KEY)
    except Exception:
        pass
    admin_store._settings.clear()
    for key in (
        "CERBERUS_AUTO_SCALE",
        "CERBERUS_AUTO_TRAIN",
        "CERBERUS_LEARNING_TICK",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    admin_store._settings.clear()


def test_scale_tick_skips_when_off(monkeypatch):
    from security import admin_store
    from workers.scaling import DynamicScaler

    admin_store.set_ops_flag("auto_scale", False)

    called = {"n": 0}

    def boom(self):
        called["n"] += 1
        return {}

    monkeypatch.setattr(DynamicScaler, "scale_workers", boom)

    from orchestrator.celery_app import run_scale_workers_tick
    from orchestrator.ml.flags import effective_auto_scale

    assert effective_auto_scale() is False
    result = run_scale_workers_tick()
    assert result == {"skipped": True, "reason": "auto_scale_off"}
    assert called["n"] == 0


def test_scale_tick_runs_when_on(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_SCALE", "true")
    from workers.scaling import DynamicScaler

    expected = {"scaled": False, "reason": "test"}

    def fake_scale(self, **kwargs):
        return expected

    monkeypatch.setattr(DynamicScaler, "scale_workers", fake_scale)

    from orchestrator.celery_app import run_scale_workers_tick

    assert run_scale_workers_tick() == expected


def test_learning_tick_skips_when_off(monkeypatch):
    from security import admin_store

    admin_store.set_ops_flag("learning_tick", False)

    from orchestrator.celery_app import run_learning_tick
    from orchestrator.ml.flags import effective_learning_tick

    assert effective_learning_tick() is False
    assert run_learning_tick() == {"skipped": True, "reason": "learning_tick_off"}


def test_learning_tick_runs_when_on(monkeypatch):
    monkeypatch.setenv("CERBERUS_LEARNING_TICK", "true")

    from orchestrator.celery_app import run_learning_tick

    assert run_learning_tick() == {"harvested": 0, "refreshed": False}


def test_daily_pipeline_skips_when_off(monkeypatch):
    from security import admin_store

    admin_store.set_ops_flag("auto_train", False)

    from orchestrator.celery_app import run_daily_pipeline
    from orchestrator.ml.flags import effective_auto_train

    assert effective_auto_train() is False
    assert run_daily_pipeline() == {"skipped": True, "reason": "auto_train_off"}


def test_daily_pipeline_runs_when_on(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_TRAIN", "true")

    from orchestrator.celery_app import run_daily_pipeline

    assert run_daily_pipeline() == {"ok": True, "dry_run": True}
