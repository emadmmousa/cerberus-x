import os
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


def test_effective_defaults_false():
    from orchestrator.ml.flags import (
        effective_auto_scale,
        effective_auto_train,
        effective_learning_tick,
    )

    assert effective_auto_scale() is False
    assert effective_auto_train() is False
    assert effective_learning_tick() is False


def test_env_enables_when_no_override(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_SCALE", "true")
    from orchestrator.ml.flags import effective_auto_scale

    assert effective_auto_scale() is True


def test_admin_override_beats_env(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_SCALE", "true")
    from security import admin_store
    from orchestrator.ml.flags import effective_auto_scale

    admin_store.set_ops_flag("auto_scale", False)
    assert effective_auto_scale() is False
    admin_store.set_ops_flag("auto_scale", None)
    assert effective_auto_scale() is True


def test_set_ops_flag_rejects_unknown():
    from security import admin_store

    with pytest.raises(ValueError, match="unknown"):
        admin_store.set_ops_flag("nope", True)


def test_get_settings_includes_ops_keys():
    from security import admin_store

    admin_store.set_ops_flag("learning_tick", True)
    s = admin_store.get_settings()
    assert s["learning_tick"] is True
    assert "auto_scale" in s
    assert "auto_train" in s
