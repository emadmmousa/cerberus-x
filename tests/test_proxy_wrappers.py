from unittest.mock import patch

from tools.wrappers import gobuster, hydra, sqlmap
from tools.wrappers._proxy import proxy_meta


def test_sqlmap_adds_proxy_flag_without_secrets(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers._proxy.ensure_worker_proxy"):
        with patch(
            "tools.wrappers._proxy._preflight_upstream_note", return_value=None
        ):
            with patch(
                "tools.wrappers.sqlmap.subprocess.check_output", return_value="ok"
            ) as mock:
                result = sqlmap.scan(
                    "example.com", use_proxy=True, proxy_protocol="http"
                )
    cmd = mock.call_args[0][0]
    assert "--proxy" in cmd
    assert "http://127.0.0.1:18080" in cmd
    assert "secret" not in cmd
    assert result["proxy"]["mode"] == "local_proxy"


def test_sqlmap_proxy_off_unchanged(monkeypatch):
    with patch("tools.wrappers.sqlmap.subprocess.check_output", return_value="ok") as mock:
        sqlmap.scan("example.com", use_proxy=False)
    cmd = mock.call_args[0][0]
    assert "--proxy" not in cmd


def test_hydra_sets_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers._proxy.ensure_worker_proxy"):
        with patch(
            "tools.wrappers._proxy._preflight_upstream_note", return_value=None
        ):
            with patch("tools.wrappers.hydra.subprocess.run") as mock:
                mock.return_value.stdout = ""
                mock.return_value.stderr = ""
                mock.return_value.returncode = 0
                hydra.scan("example.com", use_proxy=True)
    env = mock.call_args.kwargs.get("env")
    assert env is not None
    assert env["HYDRA_PROXY_HTTP"] == "http://127.0.0.1:18080"
    assert "secret" not in env["HYDRA_PROXY_HTTP"]


def test_gobuster_preflight_inherits_proxy_env(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers._proxy.ensure_worker_proxy"):
        with patch(
            "tools.wrappers._proxy._preflight_upstream_note", return_value=None
        ):
            with patch(
                "tools.wrappers.gobuster.subprocess.check_output", return_value=""
            ) as mock_run:
                with patch(
                    "tools.wrappers.gobuster._probe_exclude_length", return_value=None
                ):
                    gobuster.scan(
                        "https://example.com",
                        args=["dir", "-u", "https://example.com", "-q"],
                        use_proxy=True,
                    )
    env = mock_run.call_args.kwargs.get("env") or {}
    assert env.get("HTTP_PROXY") == "http://127.0.0.1:18080"
    assert "secret" not in env.get("HTTP_PROXY", "")


def test_proxy_meta_falls_back_direct_when_oxylabs_unreachable(monkeypatch):
    monkeypatch.setenv("OXYLABS_PROXY_USERNAME", "u")
    monkeypatch.setenv("OXYLABS_PROXY_PASSWORD", "secret")
    with patch("tools.wrappers._proxy.ensure_worker_proxy"):
        with patch(
            "tools.wrappers._proxy._preflight_upstream_note",
            return_value="oxylabs upstream unreachable: TimeoutError",
        ):
            resolved, meta = proxy_meta("ffuf", True, "http")
    assert resolved["flags"] == []
    assert resolved["env"] == {}
    assert meta["mode"] == "direct_fallback"
    assert meta["enabled"] is False
    assert meta["requested"] is True
    assert "fell back to direct" in meta["note"]
