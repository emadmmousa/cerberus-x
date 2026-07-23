"""Findings query service with org scoping."""

from __future__ import annotations

from typing import Any, Optional

from security.rbac import ForbiddenOrg, JobNotFound, get_job_for_tenant
from orchestrator.services.results import resolve_org_filter


def fetch_findings(
    *,
    job_id: Optional[str] = None,
    target: Optional[str] = None,
    severity: Optional[str] = None,
    org_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    from orchestrator.findings import list_findings
    from orchestrator.job_store import playbook_jobs
    from security.rbac import rbac_enforce_enabled

    org = resolve_org_filter(query_org=org_id)
    if job_id and job_id in playbook_jobs:
        try:
            get_job_for_tenant(job_id)
        except ForbiddenOrg:
            if rbac_enforce_enabled():
                raise
        except JobNotFound:
            pass
    return list_findings(
        org_id=org,
        job_id=job_id,
        target=target,
        severity=severity,
        limit=limit,
        offset=offset,
    )


def export_findings(
    job_id: str,
    *,
    target: Optional[str] = None,
    org_id: Optional[str] = None,
) -> dict[str, Any]:
    from orchestrator.findings import findings_export_payload
    from orchestrator.job_store import playbook_jobs

    org = resolve_org_filter(query_org=org_id)
    if job_id in playbook_jobs:
        get_job_for_tenant(job_id)
    return findings_export_payload(job_id=job_id, target=target, org_id=org)
