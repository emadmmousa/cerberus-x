import importlib

import orchestrator.celeryconfig as celeryconfig


def test_builds_redis_url_from_password(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss:word")
    monkeypatch.setenv("REDIS_HOST", "redis-service")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.delenv("REDIS_URL", raising=False)
    reloaded = importlib.reload(celeryconfig)
    assert reloaded.REDIS_URL.startswith("redis://:p%40ss%3Aword@redis-service:6379/")


def test_replaces_unexpanded_placeholder(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    monkeypatch.setenv("REDIS_HOST", "redis-service")
    monkeypatch.setenv(
        "REDIS_URL",
        "redis://:$(REDIS_PASSWORD)@redis-service:6379/0",
    )
    reloaded = importlib.reload(celeryconfig)
    assert "$(REDIS_PASSWORD)" not in reloaded.REDIS_URL
    assert "secret" in reloaded.REDIS_URL


def test_host_wins_over_stale_compose_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    monkeypatch.setenv("REDIS_HOST", "redis-service")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379")
    reloaded = importlib.reload(celeryconfig)
    assert reloaded.REDIS_URL == "redis://:secret@redis-service:6379/0"
    assert "redis://redis:" not in reloaded.REDIS_URL
