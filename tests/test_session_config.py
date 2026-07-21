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

    assert secret_key_is_insecure("cerberus-x-secret") is True
    assert secret_key_is_insecure("real-secret") is False
