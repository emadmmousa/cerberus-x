"""Auth helpers — OAuth/LDAP optional; local session always works."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Optional

from flask import jsonify, request, session

from security.audit import audit_log
from utils.config import get_config
from utils.redis_utils import get_redis

logger = logging.getLogger(__name__)

# Optional OAuth object for Flask init_app compatibility.
try:
    from authlib.integrations.flask_client import OAuth  # type: ignore

    oauth = OAuth()
except Exception:  # pragma: no cover

    class _NoopOAuth:
        def init_app(self, app):
            return None

        def register(self, *a, **k):
            return None

    oauth = _NoopOAuth()

google = None
github = None


class AuthManager:
    HONEYPOT_ACCOUNTS = frozenset(
        {"admin_honeypot", "root_honeypot", "superuser_fake", "audit_trap"}
    )

    @staticmethod
    def oauth_login(provider: str = "google"):
        cfg = get_config()
        if provider == "google" and not cfg.get("GOOGLE_CLIENT_ID"):
            return jsonify({"error": "Google OAuth not configured"}), 503
        if provider == "github" and not cfg.get("GITHUB_CLIENT_ID"):
            return jsonify({"error": "GitHub OAuth not configured"}), 503
        return (
            jsonify(
                {
                    "error": "OAuth provider libraries not fully configured",
                    "provider": provider,
                    "hint": "Set client id/secret env vars and install authlib",
                }
            ),
            501,
        )

    @staticmethod
    def oauth_callback(provider: str = "google"):
        return jsonify({"error": "OAuth callback not configured"}), 501

    @staticmethod
    def ldap_login(username: str, password: str):
        cfg = get_config()
        server = (cfg.get("LDAP_SERVER") or "").strip()
        if not server:
            return jsonify({"error": "LDAP not configured"}), 503
        try:
            from ldap3 import ALL, Connection, Server

            base = cfg.get("LDAP_BASE_DN") or ""
            srv = Server(server, get_info=ALL)
            conn = Connection(
                srv, user=f"cn={username},{base}", password=password, auto_bind=True
            )
            if conn.bound:
                return AuthManager._finalize_login(username, "ldap")
            audit_log(
                "AUTH_FAILED",
                {"username": username, "method": "ldap", "ip": request.remote_addr},
            )
            return jsonify({"error": "Invalid credentials"}), 401
        except ImportError:
            return jsonify({"error": "ldap3 not installed"}), 503
        except Exception as exc:
            logger.error("LDAP error: %s", exc)
            return jsonify({"error": "LDAP unavailable"}), 503

    @staticmethod
    def local_login(username: str, password: str):
        """Local login against the admin user store (Redis-backed).

        Falls back to FIREBREAK_ADMIN_USER / FIREBREAK_ADMIN_PASSWORD when the
        store has no password for the seeded admin (fresh installs).
        """
        # Primary: user directory managed from the admin console.
        try:
            from security.admin_store import verify_credentials

            rec = verify_credentials(username, password)
            if rec:
                return AuthManager._finalize_login(
                    username,
                    "local",
                    role=rec.get("role"),
                    org_id=rec.get("org_id"),
                )
        except Exception as exc:  # pragma: no cover - store optional
            logger.debug("admin_store login skipped: %s", exc)

        # Fallback: env admin credentials (first boot before password set).
        expected_user = os.environ.get("FIREBREAK_ADMIN_USER", "admin")
        expected_pass = os.environ.get("FIREBREAK_ADMIN_PASSWORD", "")
        if expected_pass and username == expected_user and password == expected_pass:
            return AuthManager._finalize_login(username, "local", role="admin")
        audit_log(
            "AUTH_FAILED",
            {"username": username, "method": "local", "ip": request.remote_addr},
            severity="high",
        )
        return jsonify({"error": "Invalid credentials"}), 401

    @staticmethod
    def _finalize_login(
        identifier: str,
        method: str,
        provider: Optional[str] = None,
        role: Optional[str] = None,
        org_id: Optional[str] = None,
    ):
        if identifier in AuthManager.HONEYPOT_ACCOUNTS:
            audit_log(
                "HONEYPOT_HIT",
                {"account": identifier, "ip": request.remote_addr},
                severity="critical",
            )
            try:
                from services.deception import DeceptionEngine

                DeceptionEngine().deploy_honeypot("http", 8080)
            except Exception:
                pass
            return jsonify({"error": "Account locked"}), 403

        ip = request.remote_addr or "unknown"
        risk = AuthManager._calculate_risk(identifier, ip)
        if risk > 0.6:
            AuthManager._send_mfa_code(identifier)
            session["mfa_pending"] = True
            session["mfa_identifier"] = identifier
            session["mfa_method"] = method
            audit_log("MFA_REQUIRED", {"user": identifier, "risk": risk})
            return jsonify({"mfa_required": True}), 200

        session["user"] = identifier
        session["auth_method"] = method
        default_role = (
            "admin"
            if method == "local"
            else (os.environ.get("FIREBREAK_DEFAULT_ROLE") or "operator")
        )
        session["role"] = (role or default_role).lower()
        session["org_id"] = org_id or os.environ.get("FIREBREAK_DEFAULT_ORG") or "default"
        if provider:
            session["auth_provider"] = provider
        audit_log("LOGIN_SUCCESS", {"user": identifier, "method": method, "ip": ip})
        return jsonify(
            {
                "status": "authenticated",
                "user": identifier,
                "role": session.get("role"),
                "org_id": session.get("org_id"),
            }
        ), 200

    @staticmethod
    def _calculate_risk(user: str, ip: str) -> float:
        risk = 0.0
        try:
            redis = get_redis()
            threat_ips = redis.smembers("threat_ips") or set()
            if ip in threat_ips:
                risk += 0.4
            hour = time.gmtime().tm_hour
            if hour < 8 or hour > 18:
                risk += 0.2
            last_ip = redis.get(f"user:{user}:last_ip")
            if last_ip and last_ip != ip:
                risk += 0.2
        except Exception:
            pass
        return min(risk, 1.0)

    @staticmethod
    def _send_mfa_code(user: str) -> str:
        code = str(random.randint(100000, 999999))
        try:
            get_redis().setex(f"mfa:{user}", 300, code)
        except Exception:
            pass
        logger.info("MFA code generated for %s", user)
        return code
