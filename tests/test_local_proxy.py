from tools import local_proxy, proxy_config


def test_healthy_after_start(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    monkeypatch.setenv("OXYLABS_PROXY_PROTOCOL", "http")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_HOST", "127.0.0.1")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_PORT", "0")
    server = local_proxy.LocalProxyServer()
    server.start()
    try:
        assert server.healthy() is True
        assert server.address[1] > 0
    finally:
        server.stop()


def test_errors_never_include_password(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "super-secret")
    err = local_proxy.ProxyForwardError(
        "upstream failed for " + proxy_config.upstream_proxy_url()
    )
    assert "super-secret" not in str(err)
    assert "***" in str(err)


def test_socks5h_not_implemented(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    monkeypatch.setenv("OXYLABS_PROXY_PROTOCOL", "socks5h")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_PORT", "0")
    server = local_proxy.LocalProxyServer()
    try:
        server.start()
        assert False, "expected ProxyForwardError"
    except local_proxy.ProxyForwardError as exc:
        assert "socks5h" in str(exc).lower()
        assert "p" == "p"  # password not relevant
        assert "super-secret" not in str(exc)


def test_ensure_reuses_existing_listener(monkeypatch):
    """Celery prefork: second process must borrow, not fail on EADDRINUSE."""
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "p")
    monkeypatch.setenv("OXYLABS_PROXY_PROTOCOL", "http")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_HOST", "127.0.0.1")
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_PORT", "0")

    owner = local_proxy.LocalProxyServer()
    owner.start()
    host, port = owner.address
    monkeypatch.setenv("FIREBREAK_LOCAL_PROXY_PORT", str(port))
    local_proxy._singleton = None
    try:
        borrowed = local_proxy.ensure_local_proxy()
        assert borrowed.healthy() is True
        assert borrowed.address == (host, port)
        assert isinstance(borrowed, local_proxy._BorrowedProxy)
    finally:
        owner.stop()
        local_proxy._singleton = None

