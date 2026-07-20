"""MCP API key authentication."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from flask import Request, jsonify


def mcp_enabled() -> bool:
    return os.environ.get("CERBERUS_MCP_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def expected_api_key() -> str:
    return (os.environ.get("CERBERUS_MCP_API_KEY") or "").strip()


def extract_api_key(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.headers.get("X-API-Key") or "").strip() or None


def require_api_key(request: Request):
    """Return a Flask response on failure, else None."""
    if not mcp_enabled():
        return jsonify({"error": "MCP disabled"}), 503
    expected = expected_api_key()
    if not expected:
        return jsonify({"error": "CERBERUS_MCP_API_KEY is not configured"}), 503
    provided = extract_api_key(request)
    if not provided or not hmac.compare_digest(provided, expected):
        return jsonify({"error": "unauthorized"}), 401
    return None
