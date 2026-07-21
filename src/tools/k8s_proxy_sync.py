"""Best-effort Kubernetes Secret/ConfigMap sync for proxy settings."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import requests


def in_cluster() -> bool:
    return bool(os.getenv("KUBERNETES_SERVICE_HOST"))


def _sa_token() -> str:
    path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def _sa_namespace() -> str:
    path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except FileNotFoundError:
        return os.getenv("FIREBREAK_K8S_NAMESPACE", "firebreak")


def _api_base() -> str:
    host = os.environ["KUBERNETES_SERVICE_HOST"]
    port = os.getenv("KUBERNETES_SERVICE_PORT", "443")
    return f"https://{host}:{port}"


def sync_proxy_to_kubernetes(creds: dict[str, Any]) -> dict[str, Any]:
    if not in_cluster():
        return {"ok": False, "error": "not in cluster"}
    try:
        token = _sa_token()
        namespace = _sa_namespace()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/strategic-merge-patch+json",
        }
        verify = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
        base = _api_base()

        secret_body = {
            "data": {
                "OXYLABS_PROXY_USERNAME": base64.b64encode(
                    str(creds["username"]).encode()
                ).decode(),
                "OXYLABS_PROXY_PASSWORD": base64.b64encode(
                    str(creds["password"]).encode()
                ).decode(),
            }
        }
        secret_url = (
            f"{base}/api/v1/namespaces/{namespace}/secrets/firebreak-secrets"
        )
        secret_resp = requests.patch(
            secret_url,
            headers=headers,
            data=json.dumps(secret_body),
            verify=verify,
            timeout=10,
        )
        if secret_resp.status_code not in {200, 201}:
            return {
                "ok": False,
                "error": f"secret patch failed: HTTP {secret_resp.status_code}",
            }

        cm_body = {
            "data": {
                "OXYLABS_PROXY_HOST": str(creds.get("host") or "pr.oxylabs.io"),
                "OXYLABS_PROXY_PORT": str(creds.get("port") or 7777),
                "OXYLABS_PROXY_PROTOCOL": str(creds.get("protocol") or "http"),
            }
        }
        cm_url = (
            f"{base}/api/v1/namespaces/{namespace}/configmaps/firebreak-config"
        )
        cm_resp = requests.patch(
            cm_url,
            headers=headers,
            data=json.dumps(cm_body),
            verify=verify,
            timeout=10,
        )
        if cm_resp.status_code not in {200, 201}:
            return {
                "ok": False,
                "error": f"configmap patch failed: HTTP {cm_resp.status_code}",
            }
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def clear_proxy_from_kubernetes() -> dict[str, Any]:
    return sync_proxy_to_kubernetes(
        {
            "username": "",
            "password": "",
            "host": "pr.oxylabs.io",
            "port": 7777,
            "protocol": "http",
        }
    )
