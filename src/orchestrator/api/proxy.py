"""Proxy settings controllers."""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from security.rbac import Role, require_role
from tools.proxy_config import credentials_configured
from tools import proxy_settings
from tools.env_file import clear_oxylabs_keys, upsert_oxylabs_keys
from tools.k8s_proxy_sync import sync_proxy_to_kubernetes

proxy_bp = Blueprint("proxy_api", __name__)


def _env_file_path() -> str:
    return os.getenv("FIREBREAK_ENV_FILE", "/app/.env")


def _settings_response(creds: dict | None, *, source: str, **extra):
    body = proxy_settings.public_view(creds, source=source)
    body.update(extra)
    return body


@proxy_bp.get("/api/proxy/status")
@require_role(Role.VIEWER)
def proxy_status():
    flagged = os.getenv("OXYLABS_PROXY_CONFIGURED", "").lower() in {
        "1",
        "true",
        "yes",
    }
    return jsonify({"configured": credentials_configured() or flagged})


@proxy_bp.get("/api/proxy/settings")
@require_role(Role.OPERATOR)
def proxy_settings_get():
    creds = proxy_settings.load_credentials()
    source = (creds or {}).get("source", "none") if creds else "none"
    return jsonify(_settings_response(creds, source=source))


@proxy_bp.put("/api/proxy/settings")
@require_role(Role.ADMIN)
def proxy_settings_put():
    body = request.get_json(silent=True) or {}
    existing = proxy_settings.load_settings() or proxy_settings.load_credentials()
    try:
        merged = proxy_settings.merge_put_body(body, existing)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        proxy_settings.save_settings(merged)
    except Exception as exc:
        return jsonify({"error": f"redis write failed: {exc}"}), 503

    redis_status = {"ok": True}
    try:
        upsert_oxylabs_keys(
            _env_file_path(),
            {
                "OXYLABS_PROXY_USERNAME": merged["username"],
                "OXYLABS_PROXY_PASSWORD": merged["password"],
                "OXYLABS_PROXY_HOST": merged["host"],
                "OXYLABS_PROXY_PORT": str(merged["port"]),
                "OXYLABS_PROXY_PROTOCOL": merged["protocol"],
            },
        )
        env_status: dict = {"ok": True}
    except Exception as exc:
        env_status = {"ok": False, "error": str(exc)}

    k8s_status = sync_proxy_to_kubernetes(merged)
    view = _settings_response(
        {**merged, "source": "redis"},
        source="redis",
        ok=True,
        redis=redis_status,
        env=env_status,
        k8s=k8s_status,
    )
    return jsonify(view)


@proxy_bp.post("/api/proxy/test")
@require_role(Role.OPERATOR)
def proxy_settings_test():
    from tools.wrappers._proxy import probe_upstream

    result = probe_upstream()
    status = 200 if result.get("ok") else 502
    return jsonify(result), status


@proxy_bp.delete("/api/proxy/settings")
@require_role(Role.ADMIN)
def proxy_settings_delete():
    purge = request.args.get("purge", "").lower() in {"1", "true", "yes"}
    try:
        proxy_settings.clear_settings()
    except Exception as exc:
        return jsonify({"error": f"redis clear failed: {exc}"}), 503

    env_status = {"ok": True}
    k8s_status: dict = {"ok": True}
    if purge:
        try:
            clear_oxylabs_keys(_env_file_path())
        except Exception as exc:
            env_status = {"ok": False, "error": str(exc)}
        from tools.k8s_proxy_sync import clear_proxy_from_kubernetes

        k8s_status = clear_proxy_from_kubernetes()

    return jsonify(
        {
            "ok": True,
            "configured": credentials_configured(),
            "source": "none"
            if not credentials_configured()
            else (proxy_settings.load_credentials() or {}).get("source", "env"),
            "redis": {"ok": True},
            "env": env_status,
            "k8s": k8s_status,
        }
    )
