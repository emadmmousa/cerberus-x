"""Application RBAC for Firebreak Wave 4 + Mission Control shell."""

from __future__ import annotations

import os
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional

from flask import g, jsonify, request, session


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


ROLE_RANK = {Role.VIEWER: 1, Role.OPERATOR: 2, Role.ADMIN: 3}


class ForbiddenOrg(Exception):
    """Job exists but belongs to another org."""


class JobNotFound(Exception):
    """Mission / job id unknown."""


def configured_admin_user() -> str:
    return (os.environ.get("FIREBREAK_ADMIN_USER") or "admin").strip() or "admin"


def rbac_enforce_enabled() -> bool:
    # Runtime override from the admin console takes precedence over env.
    try:
        from security.admin_store import rbac_enforce_override

        override = rbac_enforce_override()
        if override is not None:
            return override
    except Exception:
        pass
    return (os.environ.get("FIREBREAK_RBAC_ENFORCE") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def service_role_header_enabled() -> bool:
    return (os.environ.get("FIREBREAK_SERVICE_ROLE_HEADER") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def role_from_session() -> Role:
    raw = (session.get("role") or os.environ.get("FIREBREAK_DEFAULT_ROLE") or "operator").lower()
    try:
        return Role(raw)
    except ValueError:
        return Role.OPERATOR


def resolve_role() -> Role:
    """Session role; optional X-Firebreak-Role only when service header flag is on."""
    role = role_from_session()
    if service_role_header_enabled():
        hdr = (request.headers.get("X-Firebreak-Role") or "").lower()
        if hdr in {r.value for r in Role}:
            role = Role(hdr)
    g.firebreak_role = role
    return role


def tenant_id() -> str:
    org = (
        request.headers.get("X-Firebreak-Org")
        or session.get("org_id")
        or os.environ.get("FIREBREAK_DEFAULT_ORG")
        or "default"
    )
    # Non-admins may not spoof org via header when RBAC is enforced.
    if rbac_enforce_enabled() and request.headers.get("X-Firebreak-Org"):
        if ROLE_RANK[resolve_role()] < ROLE_RANK[Role.ADMIN]:
            return (
                session.get("org_id")
                or os.environ.get("FIREBREAK_DEFAULT_ORG")
                or "default"
            )
    return org


def session_authenticated() -> bool:
    if session.get("user"):
        return True
    return bool(session.get("auth_method"))


def require_auth() -> Callable:
    """When RBAC enforce is on, require an authenticated session for protected routes."""

    def decorator(fn: Callable):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not rbac_enforce_enabled():
                return fn(*args, **kwargs)
            if not session_authenticated():
                return jsonify({"error": "unauthorized"}), 401
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def require_role(minimum: Role) -> Callable:
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not rbac_enforce_enabled():
                return fn(*args, **kwargs)
            if not session_authenticated():
                return jsonify({"error": "unauthorized"}), 401
            role = resolve_role()
            if ROLE_RANK[role] < ROLE_RANK[minimum]:
                return jsonify({"error": "forbidden", "required": minimum.value}), 403
            return fn(*args, **kwargs)

        return wrapped

    return decorator


def assert_job_org(job: dict[str, Any], *, allow_missing_org: bool = True) -> None:
    """Raise ForbiddenOrg if job.org_id does not match tenant."""
    job_org = job.get("org_id")
    if job_org is None or job_org == "":
        if allow_missing_org:
            return
        raise ForbiddenOrg("mission missing org_id")
    if str(job_org) != str(tenant_id()):
        # Admins may cross-org when they set X-Firebreak-Org explicitly.
        if (
            rbac_enforce_enabled()
            and ROLE_RANK[resolve_role()] >= ROLE_RANK[Role.ADMIN]
            and request.headers.get("X-Firebreak-Org")
        ):
            return
        if str(job_org) != str(tenant_id()):
            raise ForbiddenOrg("org mismatch")


def get_job_for_tenant(job_id: str) -> dict[str, Any]:
    """Load playbook job and enforce org. Raises JobNotFound / ForbiddenOrg."""
    from orchestrator.job_store import playbook_jobs

    if job_id not in playbook_jobs:
        raise JobNotFound(job_id)
    job = playbook_jobs[job_id]
    assert_job_org(job)
    return job


def job_access_error_response(exc: Exception):
    if isinstance(exc, JobNotFound):
        return jsonify({"error": "mission not found"}), 404
    if isinstance(exc, ForbiddenOrg):
        return jsonify({"error": "forbidden", "detail": "org mismatch"}), 403
    raise exc


def me_payload() -> dict[str, Any]:
    from security.edition import feature_flags

    user = session.get("user")
    return {
        "authenticated": bool(user) or bool(session.get("auth_method")),
        "user": user,
        "role": role_from_session().value,
        "org_id": tenant_id(),
        "auth_method": session.get("auth_method"),
        "rbac_enforce": rbac_enforce_enabled(),
        "enforce": rbac_enforce_enabled(),
        "edition": feature_flags(),
        "service_role_header": service_role_header_enabled(),
    }
