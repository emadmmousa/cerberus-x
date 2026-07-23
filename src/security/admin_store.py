"""Admin IAM store: users, organizations, and runtime settings.

Redis-backed with an in-process fallback (mirrors the job_store pattern so
orchestrator replicas share state). Lab-grade: passwords are hashed with
werkzeug PBKDF2; there is no email verification or password-reset flow.

Runtime settings (``rbac_enforce``, ``edition``, auth-method config) override
environment defaults so an admin can flip them from the console without a
redeploy. ``None`` means "defer to the environment variable".
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Optional

from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

USERS_KEY = "firebreak:admin:users"
ORGS_KEY = "firebreak:admin:orgs"
SETTINGS_KEY = "firebreak:admin:settings"

VALID_ROLES = ("viewer", "operator", "admin")
VALID_EDITIONS = ("community", "pro")
# Auth methods the console can enable. auth0 is fully integrated; google and
# github are OAuth integrations that ship as "start it" stubs (config-gated).
AUTH_METHODS = ("local", "auth0", "google", "github")
OPS_FLAGS = frozenset({"auto_scale", "auto_train", "learning_tick"})


def _redis():
    try:
        from utils.redis_utils import get_redis

        return get_redis()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# In-process fallback caches (authoritative when Redis is unavailable).
# ---------------------------------------------------------------------------
_users: dict[str, dict[str, Any]] = {}
_orgs: dict[str, dict[str, Any]] = {}
_settings: dict[str, Any] = {}
_seeded = False


def _now() -> float:
    return round(time.time(), 3)


def _load_map(key: str, cache: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    r = _redis()
    if r is None:
        return cache
    try:
        raw = r.get(key)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                cache.clear()
                cache.update(data)
    except Exception as exc:
        logger.debug("admin_store load %s skipped: %s", key, exc)
    return cache


def _save_map(key: str, cache: dict[str, dict[str, Any]]) -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.set(key, json.dumps(cache, default=str))
    except Exception as exc:
        logger.debug("admin_store save %s skipped: %s", key, exc)


def _public_user(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "username": rec.get("username"),
        "role": rec.get("role"),
        "org_id": rec.get("org_id"),
        "auth_method": rec.get("auth_method"),
        "disabled": bool(rec.get("disabled")),
        "created_at": rec.get("created_at"),
        "updated_at": rec.get("updated_at"),
        "has_password": bool(rec.get("password_hash")),
    }


def ensure_seed() -> None:
    """Seed default org + env admin user on first access (idempotent)."""
    global _seeded
    _load_map(ORGS_KEY, _orgs)
    _load_map(USERS_KEY, _users)
    _load_settings()

    changed_orgs = False
    default_org = (os.environ.get("FIREBREAK_DEFAULT_ORG") or "default").strip() or "default"
    if default_org not in _orgs:
        _orgs[default_org] = {
            "id": default_org,
            "name": "Default",
            "created_at": _now(),
        }
        changed_orgs = True
    if changed_orgs:
        _save_map(ORGS_KEY, _orgs)

    admin_user = (os.environ.get("FIREBREAK_ADMIN_USER") or "admin").strip() or "admin"
    if admin_user not in _users:
        admin_pass = os.environ.get("FIREBREAK_ADMIN_PASSWORD") or ""
        _users[admin_user] = {
            "username": admin_user,
            "role": "admin",
            "org_id": default_org,
            "auth_method": "local",
            "disabled": False,
            "password_hash": generate_password_hash(admin_pass) if admin_pass else "",
            "seeded": True,
            "created_at": _now(),
            "updated_at": _now(),
        }
        _save_map(USERS_KEY, _users)
    _seeded = True


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def list_users() -> list[dict[str, Any]]:
    ensure_seed()
    _load_map(USERS_KEY, _users)
    return sorted(
        (_public_user(u) for u in _users.values()),
        key=lambda u: (u.get("username") or ""),
    )


def get_user(username: str) -> Optional[dict[str, Any]]:
    ensure_seed()
    _load_map(USERS_KEY, _users)
    return _users.get((username or "").strip())


def create_user(
    *,
    username: str,
    password: str = "",
    role: str = "viewer",
    org_id: str = "default",
    auth_method: str = "local",
) -> dict[str, Any]:
    ensure_seed()
    username = (username or "").strip()
    if not username:
        raise ValueError("username is required")
    if username in _users:
        raise ValueError("user already exists")
    role = _valid_role(role)
    auth_method = _valid_auth_method(auth_method)
    org_id = (org_id or "default").strip() or "default"
    if org_id not in _orgs:
        raise ValueError(f"unknown org: {org_id}")
    rec = {
        "username": username,
        "role": role,
        "org_id": org_id,
        "auth_method": auth_method,
        "disabled": False,
        "password_hash": generate_password_hash(password) if password else "",
        "created_at": _now(),
        "updated_at": _now(),
    }
    _users[username] = rec
    _save_map(USERS_KEY, _users)
    return _public_user(rec)


def update_user(username: str, **changes: Any) -> dict[str, Any]:
    ensure_seed()
    username = (username or "").strip()
    rec = _users.get(username)
    if not rec:
        raise ValueError("user not found")
    if "role" in changes and changes["role"] is not None:
        rec["role"] = _valid_role(changes["role"])
    if "org_id" in changes and changes["org_id"]:
        org_id = str(changes["org_id"]).strip()
        if org_id not in _orgs:
            raise ValueError(f"unknown org: {org_id}")
        rec["org_id"] = org_id
    if "auth_method" in changes and changes["auth_method"]:
        rec["auth_method"] = _valid_auth_method(changes["auth_method"])
    if "disabled" in changes and changes["disabled"] is not None:
        rec["disabled"] = bool(changes["disabled"])
    if changes.get("password"):
        rec["password_hash"] = generate_password_hash(str(changes["password"]))
    rec["updated_at"] = _now()
    _users[username] = rec
    _save_map(USERS_KEY, _users)
    return _public_user(rec)


def delete_user(username: str) -> bool:
    ensure_seed()
    username = (username or "").strip()
    if username not in _users:
        return False
    admins = [
        u
        for u in _users.values()
        if u.get("role") == "admin" and not u.get("disabled")
    ]
    if _users[username].get("role") == "admin" and len(admins) <= 1:
        raise ValueError("cannot delete the last active admin")
    _users.pop(username, None)
    _save_map(USERS_KEY, _users)
    return True


def verify_credentials(username: str, password: str) -> Optional[dict[str, Any]]:
    """Return the user record on a valid local password, else None."""
    rec = get_user(username)
    if not rec or rec.get("disabled"):
        return None
    if not rec.get("password_hash"):
        return None
    if check_password_hash(rec["password_hash"], password or ""):
        return rec
    return None


def username_available(username: str, *, exclude: Optional[str] = None) -> bool:
    """Return True when ``username`` is free (or unchanged for ``exclude``)."""
    ensure_seed()
    _load_map(USERS_KEY, _users)
    username = (username or "").strip()
    if not username:
        return False
    if exclude and username == (exclude or "").strip():
        return True
    return username not in _users


def rename_user(old_username: str, new_username: str) -> dict[str, Any]:
    """Change the account key and username field."""
    ensure_seed()
    old_username = (old_username or "").strip()
    new_username = (new_username or "").strip()
    if not old_username or not new_username:
        raise ValueError("username is required")
    if old_username == new_username:
        rec = _users.get(old_username)
        if not rec:
            raise ValueError("user not found")
        return _public_user(rec)
    if new_username in _users:
        raise ValueError("username already taken")
    rec = _users.pop(old_username, None)
    if not rec:
        raise ValueError("user not found")
    rec["username"] = new_username
    rec["updated_at"] = _now()
    _users[new_username] = rec
    _save_map(USERS_KEY, _users)
    return _public_user(rec)


def get_profile_payload(username: str) -> Optional[dict[str, Any]]:
    """Public profile fields plus org display name when present."""
    rec = get_user(username)
    if not rec:
        return None
    out = _public_user(rec)
    org_id = rec.get("org_id")
    org = _orgs.get(org_id) if org_id else None
    if org:
        out["org_name"] = org.get("name")
    members = sum(1 for u in _users.values() if u.get("org_id") == org_id)
    out["can_edit_org_name"] = bool(org_id and members == 1 and org_id in _orgs)
    out["can_edit_username"] = rec.get("auth_method") == "local" and not rec.get("disabled")
    out["can_edit_password"] = bool(
        rec.get("auth_method") == "local"
        and rec.get("password_hash")
        and not rec.get("disabled")
    )
    return out


def update_self_profile(
    username: str,
    *,
    current_password: str,
    new_username: Optional[str] = None,
    new_password: Optional[str] = None,
    org_name: Optional[str] = None,
) -> dict[str, Any]:
    """Self-service profile updates (local accounts with password verification)."""
    ensure_seed()
    username = (username or "").strip()
    rec = _users.get(username)
    if not rec or rec.get("disabled"):
        raise ValueError("user not found")
    if rec.get("auth_method") != "local":
        raise ValueError("profile is managed by your identity provider")
    if not rec.get("password_hash"):
        raise ValueError("set a password in admin settings before changing profile")
    if not verify_credentials(username, current_password or ""):
        raise ValueError("current password is incorrect")

    new_username = (new_username or "").strip() or None
    if new_username and new_username != username:
        if len(new_username) < 3:
            raise ValueError("username must be at least 3 characters")
        if not username_available(new_username, exclude=username):
            raise ValueError("username already taken")
        rec = _users.pop(username)
        rec["username"] = new_username
        username = new_username

    if new_password:
        if len(new_password) < 8:
            raise ValueError("password must be at least 8 characters")
        rec["password_hash"] = generate_password_hash(new_password)

    if org_name is not None:
        org_id = rec.get("org_id")
        members = sum(1 for u in _users.values() if u.get("org_id") == org_id)
        if not org_id or org_id not in _orgs or members != 1:
            raise ValueError("organization name cannot be changed")
        org_rec = _orgs[org_id]
        org_rec["name"] = (org_name or org_rec.get("name") or org_id).strip()
        org_rec["updated_at"] = _now()
        _orgs[org_id] = org_rec
        _save_map(ORGS_KEY, _orgs)

    rec["updated_at"] = _now()
    _users[username] = rec
    _save_map(USERS_KEY, _users)
    return get_profile_payload(username) or _public_user(rec)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------
def list_orgs() -> list[dict[str, Any]]:
    ensure_seed()
    _load_map(ORGS_KEY, _orgs)
    counts: dict[str, int] = {}
    for u in _users.values():
        counts[u.get("org_id")] = counts.get(u.get("org_id"), 0) + 1
    out = []
    for org in _orgs.values():
        row = dict(org)
        row["user_count"] = counts.get(org.get("id"), 0)
        out.append(row)
    return sorted(out, key=lambda o: (o.get("id") or ""))


def create_org(*, org_id: str, name: str = "") -> dict[str, Any]:
    ensure_seed()
    org_id = (org_id or "").strip()
    if not org_id:
        raise ValueError("org id is required")
    if org_id in _orgs:
        raise ValueError("org already exists")
    rec = {"id": org_id, "name": (name or org_id).strip(), "created_at": _now()}
    _orgs[org_id] = rec
    _save_map(ORGS_KEY, _orgs)
    return rec


def update_org(org_id: str, *, name: str) -> dict[str, Any]:
    ensure_seed()
    rec = _orgs.get((org_id or "").strip())
    if not rec:
        raise ValueError("org not found")
    rec["name"] = (name or rec.get("name") or org_id).strip()
    rec["updated_at"] = _now()
    _orgs[org_id] = rec
    _save_map(ORGS_KEY, _orgs)
    return rec


def delete_org(org_id: str) -> bool:
    ensure_seed()
    org_id = (org_id or "").strip()
    if org_id not in _orgs:
        return False
    if any(u.get("org_id") == org_id for u in _users.values()):
        raise ValueError("cannot delete an org with associated users")
    if org_id == (os.environ.get("FIREBREAK_DEFAULT_ORG") or "default"):
        raise ValueError("cannot delete the default org")
    _orgs.pop(org_id, None)
    _save_map(ORGS_KEY, _orgs)
    return True


def associate_user(username: str, org_id: str) -> dict[str, Any]:
    return update_user(username, org_id=org_id)


# ---------------------------------------------------------------------------
# Runtime settings (override env defaults)
# ---------------------------------------------------------------------------
def _load_settings() -> dict[str, Any]:
    r = _redis()
    if r is not None:
        try:
            raw = r.get(SETTINGS_KEY)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    _settings.clear()
                    _settings.update(data)
        except Exception as exc:
            logger.debug("admin_store settings load skipped: %s", exc)
    return _settings


def _save_settings() -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.set(SETTINGS_KEY, json.dumps(_settings, default=str))
    except Exception as exc:
        logger.debug("admin_store settings save skipped: %s", exc)


def get_settings() -> dict[str, Any]:
    _load_settings()
    return {
        "rbac_enforce": _settings.get("rbac_enforce"),
        "edition": _settings.get("edition"),
        "auth_methods": _settings.get("auth_methods") or {},
        "auto_scale": _settings.get("auto_scale"),
        "auto_train": _settings.get("auto_train"),
        "learning_tick": _settings.get("learning_tick"),
    }


def rbac_enforce_override() -> Optional[bool]:
    _load_settings()
    val = _settings.get("rbac_enforce")
    return bool(val) if val is not None else None


def edition_override() -> Optional[str]:
    _load_settings()
    val = _settings.get("edition")
    return val if val in VALID_EDITIONS else None


def set_rbac_enforce(value: Optional[bool]) -> dict[str, Any]:
    _load_settings()
    _settings["rbac_enforce"] = None if value is None else bool(value)
    _save_settings()
    return get_settings()


def set_edition(value: Optional[str]) -> dict[str, Any]:
    _load_settings()
    if value is not None and value not in VALID_EDITIONS:
        raise ValueError(f"edition must be one of {VALID_EDITIONS}")
    _settings["edition"] = value
    _save_settings()
    return get_settings()


def set_auth_method(method: str, enabled: bool) -> dict[str, Any]:
    _load_settings()
    method = _valid_auth_method(method)
    methods = dict(_settings.get("auth_methods") or {})
    methods[method] = bool(enabled)
    _settings["auth_methods"] = methods
    _save_settings()
    return get_settings()


def _ops_override(name: str) -> Optional[bool]:
    if name not in OPS_FLAGS:
        raise ValueError(f"unknown ops flag: {name}")
    _load_settings()
    val = _settings.get(name)
    return bool(val) if val is not None else None


def auto_scale_override() -> Optional[bool]:
    return _ops_override("auto_scale")


def auto_train_override() -> Optional[bool]:
    return _ops_override("auto_train")


def learning_tick_override() -> Optional[bool]:
    return _ops_override("learning_tick")


def set_ops_flag(name: str, value: Optional[bool]) -> dict[str, Any]:
    if name not in OPS_FLAGS:
        raise ValueError(f"unknown ops flag: {name}")
    _load_settings()
    _settings[name] = None if value is None else bool(value)
    _save_settings()
    return get_settings()


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
def _valid_role(role: str) -> str:
    role = (role or "").strip().lower()
    if role not in VALID_ROLES:
        raise ValueError(f"role must be one of {VALID_ROLES}")
    return role


def _valid_auth_method(method: str) -> str:
    method = (method or "").strip().lower()
    if method not in AUTH_METHODS:
        raise ValueError(f"auth_method must be one of {AUTH_METHODS}")
    return method
