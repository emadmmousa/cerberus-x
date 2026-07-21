def test_configure_sessions_cookie_fallback(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-default")
    from flask import Flask
    from orchestrator.session_config import configure_sessions

    app = Flask("t")
    app.config["SECRET_KEY"] = "test-secret-key-not-default"
    # Force cookie path by making redis look like MemoryRedis
    info = configure_sessions(app, force_cookie=True)
    assert info["backend"] == "cookie"


def test_default_secret_flag():
    from orchestrator.session_config import secret_key_is_insecure

    assert secret_key_is_insecure("firebreak-secret") is True
    assert secret_key_is_insecure("change-me") is True
    assert secret_key_is_insecure("") is True
    assert secret_key_is_insecure("real-secret") is False


def test_get_redis_binary_disables_decode(monkeypatch):
    """Session payloads are msgpack bytes; UTF-8 decode must stay off."""
    import utils.redis_utils as ru

    ru._binary_client = None
    captured: dict = {}

    class FakeRedis:
        def ping(self):
            return True

    def fake_from_url(url, decode_responses=True, **kwargs):
        captured["decode_responses"] = decode_responses
        captured["url"] = url
        return FakeRedis()

    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    monkeypatch.setattr("redis.Redis.from_url", fake_from_url)

    client = ru.get_redis_binary()
    assert captured["decode_responses"] is False
    assert client is ru._binary_client
