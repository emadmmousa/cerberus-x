"""Request WAF — scoped so pentest payloads on /api/run are not blocked."""

from __future__ import annotations

import os
import re

from flask import jsonify, request

from security.audit import audit_log


class WAFMiddleware:
    PATTERNS = {
        "sqli": re.compile(
            r"(\b(select|insert|update|delete|drop|union|exec|declare|alter)\b."
            r"*\b(from|into|table|database)\b)",
            re.IGNORECASE,
        ),
        "xss": re.compile(
            r"(<script|javascript:|onerror=|onload=|alert\(|prompt\(|confirm\()",
            re.IGNORECASE,
        ),
        "path_traversal": re.compile(r"(\.\./|\.\.\\)"),
        "command_injection": re.compile(
            r"(;|\||`)\s*(rm|cat|curl|wget|bash|sh|powershell)\b",
            re.IGNORECASE,
        ),
    }

    # Mission / tool APIs intentionally carry attack strings — do not block them.
    ALLOWLIST_PREFIXES = (
        "/api/run",
        "/api/ai/",
        "/api/aggressive/",
        "/api/playbook",
        "/mcp",
        "/status/",
        "/results",
        "/health",
        "/ready",
        "/metrics",
        "/favicon.ico",
        "/assets/",
    )

    @staticmethod
    def enabled() -> bool:
        return os.environ.get("FIREBREAK_WAF_ENABLED", "true").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    @staticmethod
    def before_request():
        if not WAFMiddleware.enabled():
            return None
        path = request.path or "/"
        if any(path.startswith(p) for p in WAFMiddleware.ALLOWLIST_PREFIXES):
            return None
        # Protect auth / admin surfaces only.
        if not (path.startswith("/auth") or path.startswith("/api/proxy")):
            return None

        payload = dict(request.args.to_dict())
        try:
            if request.is_json:
                body = request.get_json(silent=True) or {}
                if isinstance(body, dict):
                    payload.update({k: v for k, v in body.items() if not isinstance(v, (dict, list))})
            else:
                payload.update(request.form.to_dict())
        except Exception:
            pass

        for key, value in payload.items():
            if isinstance(value, list):
                value = " ".join(str(v) for v in value)
            else:
                value = str(value)
            for name, pattern in WAFMiddleware.PATTERNS.items():
                if pattern.search(value):
                    audit_log(
                        "WAF_BLOCKED",
                        {
                            "ip": request.remote_addr,
                            "path": path,
                            "pattern": name,
                            "field": key,
                            "value": value[:200],
                        },
                        severity="high",
                    )
                    return jsonify({"error": "Invalid request"}), 400
        return None

    @staticmethod
    def after_request(response):
        return response
