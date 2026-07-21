"""Open-core edition gates (Firebreak Wave 5 scaffold).

Community edition is fully functional for self-host. ``pro`` only gates
enterprise packaging hooks (SSO require, multi-tenant defaults) when
explicitly enabled — never silently disables core scanning.
"""

from __future__ import annotations

import os
from typing import Any


def edition() -> str:
    # Runtime override from the admin console takes precedence over env.
    try:
        from security.admin_store import edition_override

        override = edition_override()
        if override:
            return override
    except Exception:
        pass
    raw = (os.environ.get("CERBERUS_EDITION") or "community").strip().lower()
    return raw if raw in {"community", "pro"} else "community"


def is_pro() -> bool:
    return edition() == "pro"


def feature_flags() -> dict[str, Any]:
    """Declarative flags for UI / status. Core tools always available."""
    pro = is_pro()
    return {
        "edition": edition(),
        "sso_packaging": pro,
        "managed_hosting_hooks": pro,
        "scaffold_marketplace": pro,
        # Always on in both editions:
        "multi_scaffold": True,
        "blackboard": True,
        "arsenal_wrappers": True,
        "own_model": True,
    }


def require_pro_packaging() -> bool:
    """When true, SSO/RBAC packaging endpoints may insist on Pro config."""
    return is_pro() and (os.environ.get("CERBERUS_PRO_PACKAGING") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
