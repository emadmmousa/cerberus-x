"""OAuth / LDAP / local authentication routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from security.auth import AuthManager

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login/<provider>")
def login(provider: str):
    if provider not in {"google", "github"}:
        return jsonify({"error": "Provider not supported"}), 400
    return AuthManager.oauth_login(provider)


@auth_bp.route("/oauth-callback/<provider>")
def oauth_callback(provider: str):
    return AuthManager.oauth_callback(provider)


@auth_bp.route("/ldap/login", methods=["POST"])
def ldap_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
    return AuthManager.ldap_login(username, password)


@auth_bp.route("/local/login", methods=["POST"])
def local_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400
    return AuthManager.local_login(username, password)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"status": "logged out"})


@auth_bp.route("/status")
def auth_status():
    if "user" in session:
        return jsonify({"authenticated": True, "user": session["user"]})
    return jsonify({"authenticated": False})
