"""Session / RBAC / OIDC status controllers."""

from __future__ import annotations

from flask import Blueprint, jsonify

from security.rbac import Role, me_payload, require_auth, require_role

session_bp = Blueprint("session_api", __name__)


@session_bp.get("/api/rbac/me")
def api_rbac_me():
    return jsonify(me_payload())


@session_bp.get("/api/oidc/status")
def api_oidc_status():
    from security.auth0_sdk import auth0_status
    from security.oidc import oidc_status

    a0 = auth0_status()
    if a0.get("configured") or a0.get("domain") or a0.get("client_id_set"):
        return jsonify(a0)
    return jsonify(oidc_status())


@session_bp.get("/api/audit/recent")
@require_role(Role.VIEWER)
def api_audit_recent():
    from flask import request

    from security.audit import recent_audit

    limit = min(int(request.args.get("limit", 40)), 200)
    event = (request.args.get("event_type") or "").strip()
    rows = recent_audit(limit=limit)
    if event:
        rows = [r for r in rows if r.get("event_type") == event]
    return jsonify({"count": len(rows), "events": rows})


@session_bp.get("/api/admin/session")
@require_auth()
def api_admin_session():
    """Admin shell: full session + packaging readiness (any authenticated when enforce)."""
    from security.pro_packaging import packaging_status, sso_readiness

    payload = me_payload()
    payload["packaging"] = packaging_status()
    payload["sso"] = sso_readiness()
    return jsonify(payload)
