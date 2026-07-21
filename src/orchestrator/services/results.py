"""Results query service (ES preferred, SQLite fallback)."""

from __future__ import annotations

from typing import Any, Optional

from security.rbac import (
    ForbiddenOrg,
    JobNotFound,
    get_job_for_tenant,
    role_from_session,
    ROLE_RANK,
    Role,
    tenant_id,
)


def resolve_org_filter(*, query_org: Optional[str] = None) -> str:
    """Org for reads: session tenant only; admin may override via query when RBAC on."""
    org = tenant_id()
    if query_org and str(query_org) != str(org):
        if ROLE_RANK[role_from_session()] >= ROLE_RANK[Role.ADMIN]:
            return str(query_org)
        # Ignore client spoof for non-admins
    return org


def fetch_results(
    *,
    target: Optional[str],
    job_id: Optional[str],
    org_id: Optional[str],
    limit: int,
    es_client: Any,
) -> list[dict[str, Any]]:
    from orchestrator.database import get_results

    from security.rbac import rbac_enforce_enabled
    from orchestrator.job_store import playbook_jobs

    org = resolve_org_filter(query_org=org_id)
    if job_id:
        # Live jobs: enforce org when present in the store (strict if RBAC on).
        if job_id in playbook_jobs:
            try:
                get_job_for_tenant(job_id)
            except ForbiddenOrg:
                if rbac_enforce_enabled():
                    raise
            except JobNotFound:
                pass
        return get_results(target, limit, job_id=job_id, org_id=org)
    if es_client is not None and getattr(es_client, "available", False):
        rows = es_client.search_results(target=target, org_id=org, limit=limit)
        if rows:
            return rows
    return get_results(target, limit, org_id=org)
