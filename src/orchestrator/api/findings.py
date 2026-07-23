"""Normalized findings controllers."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from orchestrator.services import findings as findings_svc
from security.rbac import ForbiddenOrg, JobNotFound, Role, job_access_error_response, require_role

findings_bp = Blueprint("findings_api", __name__)


@findings_bp.get("/api/findings")
@require_role(Role.VIEWER)
def api_findings_list():
    job_id = request.args.get("job_id")
    target = request.args.get("target")
    severity = request.args.get("severity")
    org_id = request.args.get("org_id")
    try:
        limit = int(request.args.get("limit") or 50)
    except ValueError:
        limit = 50
    try:
        offset = int(request.args.get("offset") or 0)
    except ValueError:
        offset = 0
    try:
        payload = findings_svc.fetch_findings(
            job_id=job_id,
            target=target,
            severity=severity,
            org_id=org_id,
            limit=limit,
            offset=offset,
        )
    except ForbiddenOrg:
        return jsonify({"error": "forbidden", "detail": "org mismatch"}), 403
    except JobNotFound as exc:
        return job_access_error_response(exc)
    return jsonify(payload)


@findings_bp.get("/api/missions/<job_id>/findings/export")
@require_role(Role.VIEWER)
def api_findings_export(job_id: str):
    target = request.args.get("target")
    org_id = request.args.get("org_id")
    try:
        payload = findings_svc.export_findings(job_id, target=target, org_id=org_id)
    except ForbiddenOrg as exc:
        return job_access_error_response(exc)
    except JobNotFound as exc:
        return job_access_error_response(exc)
    fmt = (request.args.get("format") or "json").lower()
    if fmt == "markdown":
        return (
            payload["markdown"],
            200,
            {"Content-Type": "text/markdown; charset=utf-8"},
        )
    return jsonify(payload)
