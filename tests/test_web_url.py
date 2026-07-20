from tools.wrappers import _web_url as web_url


def test_ensure_https_upgrades_http():
    assert web_url.ensure_https_url("http://example.com/path") == "https://example.com/path"
    assert web_url.ensure_https_url("example.com") == "https://example.com"


def test_https_upgrade_location_forces_https_www():
    assert (
        web_url._https_upgrade_location("http://www.example.com/", "example.com")
        == "https://www.example.com"
    )


def test_canonicalize_prefers_https_www_on_http_downgrade(monkeypatch):
    monkeypatch.setattr(
        web_url,
        "_probe_redirect",
        lambda url, timeout=8.0: "http://www.example.com/",
    )
    assert web_url.canonicalize_web_url("https://example.com") == "https://www.example.com"


def test_canonicalize_keeps_https_when_no_redirect(monkeypatch):
    monkeypatch.setattr(web_url, "_probe_redirect", lambda url, timeout=8.0: None)
    assert web_url.canonicalize_web_url("https://example.com/app") == "https://example.com/app"


def test_force_url_arg_rewrites_preexpanded_http():
    assert web_url.force_url_arg(
        ["dir", "-u", "http://takwene.com", "-w", "/tmp/w"],
        "https://www.takwene.com",
    ) == ["dir", "-u", "https://www.takwene.com", "-w", "/tmp/w"]
    assert web_url.force_url_arg(
        ["-u", "https://takwene.com/FUZZ", "-w", "/tmp/w"],
        "https://www.takwene.com",
        with_fuzz=True,
    ) == ["-u", "https://www.takwene.com/FUZZ", "-w", "/tmp/w"]


def test_gobuster_rewrites_preexpanded_http_url(monkeypatch):
    from tools.wrappers import gobuster

    monkeypatch.setattr(
        gobuster,
        "canonicalize_web_url",
        lambda target: "https://www.example.com",
    )
    monkeypatch.setattr(
        gobuster,
        "proxy_meta",
        lambda *a, **k: ({"flags": [], "env": {}}, {"enabled": False, "mode": "direct"}),
    )
    monkeypatch.setattr(gobuster, "_probe_exclude_length", lambda *a, **k: None)
    captured = {}

    def fake_run(args, env=None):
        captured["args"] = args
        return ""

    monkeypatch.setattr(gobuster, "_run", fake_run)
    result = gobuster.scan(
        "http://example.com",
        # Mimic tasks.py already expanding {{target}} to plain HTTP.
        args=["dir", "-u", "http://example.com", "-w", "/tmp/w", "-b", "404"],
    )
    assert "-u" in captured["args"]
    assert captured["args"][captured["args"].index("-u") + 1] == "https://www.example.com"
    assert result["target"] == "https://www.example.com"


def test_gobuster_uses_canonical_url(monkeypatch):
    from tools.wrappers import gobuster

    monkeypatch.setattr(
        gobuster,
        "canonicalize_web_url",
        lambda target: "https://www.example.com",
    )
    monkeypatch.setattr(
        gobuster,
        "proxy_meta",
        lambda *a, **k: ({"flags": [], "env": {}}, {"enabled": False, "mode": "direct"}),
    )
    monkeypatch.setattr(gobuster, "_probe_exclude_length", lambda *a, **k: None)
    captured = {}

    def fake_run(args, env=None):
        captured["args"] = args
        return ""

    monkeypatch.setattr(gobuster, "_run", fake_run)
    result = gobuster.scan(
        "http://example.com",
        args=["dir", "-u", "{{target}}", "-w", "/tmp/w", "-b", "404"],
    )
    assert "-u" in captured["args"]
    assert captured["args"][captured["args"].index("-u") + 1] == "https://www.example.com"
    assert result["target"] == "https://www.example.com"
