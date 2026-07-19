from tools import k8s_proxy_sync


def test_sync_not_in_cluster(monkeypatch):
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    result = k8s_proxy_sync.sync_proxy_to_kubernetes(
        {
            "username": "u",
            "password": "p",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        }
    )
    assert result == {"ok": False, "error": "not in cluster"}


def test_sync_patches_secret_and_configmap(monkeypatch):
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "443")
    monkeypatch.setattr(k8s_proxy_sync, "_sa_token", lambda: "tok")
    monkeypatch.setattr(k8s_proxy_sync, "_sa_namespace", lambda: "cerberus-x")

    calls = []

    class Resp:
        def __init__(self, code):
            self.status_code = code

    def fake_patch(url, headers=None, data=None, verify=None, timeout=None):
        calls.append({"url": url, "data": data})
        return Resp(200)

    monkeypatch.setattr(k8s_proxy_sync.requests, "patch", fake_patch)
    result = k8s_proxy_sync.sync_proxy_to_kubernetes(
        {
            "username": "u",
            "password": "p",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "socks5h",
        }
    )
    assert result == {"ok": True}
    assert len(calls) == 2
    assert "secrets/cerberus-secrets" in calls[0]["url"]
    assert "configmaps/cerberus-config" in calls[1]["url"]
    assert '"OXYLABS_PROXY_PROTOCOL": "socks5h"' in calls[1]["data"]
