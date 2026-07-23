"""OSINT breach lookup API — DeHashed + LeakCheck provider status and queries."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from orchestrator.osint.breach_branding import sanitize_breach_payload, sanitize_provider_status
from orchestrator.osint.breach_providers import dehashed_user_info, provider_status
from orchestrator.osint.breach_service import lookup_seeds
from orchestrator.osint.seeds import normalize_osint_seeds
from security.rbac import Role, require_role

osint_breach_bp = Blueprint("osint_breach_api", __name__)


@osint_breach_bp.get("/api/osint/breach/status")
@require_role(Role.VIEWER)
def breach_status():
    status = sanitize_provider_status(provider_status())
    vault = status.get("breach_vault") or {}
    if isinstance(vault, dict) and vault.get("configured"):
        vault = dict(vault)
        vault["account"] = dehashed_user_info()
        status["breach_vault"] = vault
    return jsonify(status)


@osint_breach_bp.post("/api/osint/breach/lookup")
@require_role(Role.OPERATOR)
def breach_lookup():
    body = request.get_json(silent=True) or {}
    seeds = normalize_osint_seeds(body.get("seeds") or body.get("osint_seeds"))
    if not seeds:
        return jsonify({"error": "seeds required (list of {kind, value})"}), 400
    limit = body.get("limit", 25)
    try:
        per_provider_limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        per_provider_limit = 25
    result = lookup_seeds(seeds, per_provider_limit=per_provider_limit)
    return jsonify(result)
