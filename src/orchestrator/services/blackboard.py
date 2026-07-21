"""Blackboard document service (org-scoped)."""

from __future__ import annotations

from typing import Any, Optional

from orchestrator.ai import blackboard as bb
from security.rbac import tenant_id


def list_docs(mission_id: str) -> dict[str, Any]:
    org = tenant_id()
    keys = bb.list_keys(mission_id, org_id=org)
    items = []
    for name in keys:
        doc = bb.get(mission_id, name, org_id=org)
        if doc:
            items.append(doc)
    return {"mission_id": mission_id, "org_id": org, "keys": keys, "items": items}


def get_doc(mission_id: str, name: str) -> Optional[dict[str, Any]]:
    return bb.get(mission_id, name, org_id=tenant_id())


def put_doc(
    mission_id: str,
    name: str,
    value: Any,
    *,
    ttl: int = 86400,
    expected_version: Optional[int] = None,
) -> dict[str, Any]:
    return bb.put(
        mission_id,
        name,
        value,
        ttl=ttl,
        expected_version=expected_version,
        org_id=tenant_id(),
    )
