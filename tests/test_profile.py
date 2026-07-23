"""Self-service profile: username availability, rename, password change."""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture(autouse=True)
def _clean_admin_store():
    from security import admin_store
    from utils.redis_utils import get_redis

    r = get_redis()
    for key in (admin_store.USERS_KEY, admin_store.ORGS_KEY, admin_store.SETTINGS_KEY):
        try:
            r.delete(key)
        except Exception:
            pass
    admin_store._users.clear()
    admin_store._orgs.clear()
    admin_store._settings.clear()
    admin_store._seeded = False
    yield
    for key in (admin_store.USERS_KEY, admin_store.ORGS_KEY, admin_store.SETTINGS_KEY):
        try:
            r.delete(key)
        except Exception:
            pass
    admin_store._users.clear()
    admin_store._orgs.clear()
    admin_store._settings.clear()


def _client():
    from orchestrator import dashboard

    return dashboard.app.test_client()


def _signup(client, username: str | None = None, org: str = "Acme"):
    username = username or f"user-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/auth/local/signup",
        json={"username": username, "password": "correcthorse", "org": org},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    return username


def test_profile_me_returns_editable_flags():
    c = _client()
    username = _signup(c)
    data = c.get("/api/profile/me").get_json()
    assert data["username"] == username
    assert data["can_edit_username"] is True
    assert data["can_edit_password"] is True
    assert data["can_edit_org_name"] is True
    assert data["org_name"] == "Acme"


def test_username_check_available_and_taken():
    c = _client()
    username = _signup(c)
    other = f"other-{uuid.uuid4().hex[:6]}"

    ok = c.get(f"/api/profile/username/check?username={other}").get_json()
    assert ok["available"] is True

    same = c.get(f"/api/profile/username/check?username={username}").get_json()
    assert same["available"] is True

    from security import admin_store

    admin_store.create_user(
        username=other,
        password="correcthorse",
        role="operator",
        org_id=admin_store.list_orgs()[0]["id"],
    )
    blocked = c.get(f"/api/profile/username/check?username={other}").get_json()
    assert blocked["available"] is False


def test_profile_update_username_and_password():
    c = _client()
    username = _signup(c)
    new_name = f"renamed-{uuid.uuid4().hex[:6]}"

    bad = c.patch(
        "/api/profile",
        json={"username": new_name, "current_password": "wrong"},
    )
    assert bad.status_code == 400

    updated = c.patch(
        "/api/profile",
        json={
            "username": new_name,
            "new_password": "newpassword1",
            "current_password": "correcthorse",
        },
    )
    assert updated.status_code == 200, updated.get_data(as_text=True)
    body = updated.get_json()
    assert body["username"] == new_name

    status = c.get("/auth/status").get_json()
    assert status["user"] == new_name

    login = c.post(
        "/auth/local/login",
        json={"username": new_name, "password": "newpassword1"},
    )
    assert login.status_code == 200


def test_profile_update_org_name_when_sole_member():
    c = _client()
    username = _signup(c, org="Original Org")
    updated = c.patch(
        "/api/profile",
        json={"org_name": "Renamed Org", "current_password": "correcthorse"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["org_name"] == "Renamed Org"


def test_rename_user_store_helper():
    from security import admin_store

    admin_store.create_org(org_id="solo", name="Solo")
    admin_store.create_user(
        username="alice",
        password="correcthorse",
        role="operator",
        org_id="solo",
    )
    admin_store.rename_user("alice", "alicia")
    assert admin_store.get_user("alice") is None
    assert admin_store.get_user("alicia")["username"] == "alicia"
    assert admin_store.verify_credentials("alicia", "correcthorse")
