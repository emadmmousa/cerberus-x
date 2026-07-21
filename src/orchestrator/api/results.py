"""Results controller."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from security.rbac import ForbiddenOrg, Role, require_role
from orchestrator.services import results as results_svc

results_bp = Blueprint("results_api", __name__)


@results_bp.get("/results")
@require_role(Role.VIEWER)
def results():
    from orchestrator import dashboard as dash

    target = request.args.get("target")
    job_id = request.args.get("job_id")
    org_id = request.args.get("org_id")
    limit = int(request.args.get("limit", 100))
    try:
        rows = results_svc.fetch_results(
            target=target,
            job_id=job_id,
            org_id=org_id,
            limit=limit,
            es_client=dash.es_client,
        )
    except ForbiddenOrg:
        return jsonify({"error": "forbidden", "detail": "org mismatch"}), 403
    return jsonify(rows)
