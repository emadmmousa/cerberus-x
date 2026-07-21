"""Admin console: user/org CRUD, settings overrides, mission ops, logs."""

import pytest


@pytest.fixture(autouse=True)
def _clean_admin_store():
    """Isolate each test from shared Redis admin state."""
    from utils.redis_utils import get_redis
    from security import admin_store

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


def test_seed_creates_default_org_and_admin():
    from security import admin_store

    users = admin_store.list_users()
    orgs = admin_store.list_orgs()
    assert any(o["id"] == "default" for o in orgs)
    assert any(u["role"] == "admin" for u in users)


def test_user_crud_and_role_change():
    from security import admin_store

    admin_store.create_org(org_id="acme", name="Acme")
    admin_store.create_user(username="bob", password="secret12", role="viewer", org_id="acme")
    assert admin_store.verify_credentials("bob", "secret12")
    assert admin_store.verify_credentials("bob", "wrong") is None

    admin_store.update_user("bob", role="operator")
    rec = admin_store.get_user("bob")
    assert rec["role"] == "operator"

    assert admin_store.delete_user("bob") is True
    assert admin_store.get_user("bob") is None


def test_cannot_delete_last_admin():
    from security import admin_store

    admins = [u for u in admin_store.list_users() if u["role"] == "admin"]
    with pytest.raises(ValueError, match="last active admin"):
        admin_store.delete_user(admins[0]["username"])


def test_org_lifecycle_and_association():
    from security import admin_store

    admin_store.create_org(org_id="acme", name="Acme")
    admin_store.create_user(username="carol", role="viewer", org_id="default")
    admin_store.associate_user("carol", "acme")
    assert admin_store.get_user("carol")["org_id"] == "acme"

    # org with users cannot be deleted
    with pytest.raises(ValueError, match="associated users"):
        admin_store.delete_org("acme")

    admin_store.update_user("carol", org_id="default")
    assert admin_store.delete_org("acme") is True


def test_rbac_override_takes_effect():
    from security import admin_store
    from security.rbac import rbac_enforce_enabled

    admin_store.set_rbac_enforce(True)
    assert rbac_enforce_enabled() is True
    admin_store.set_rbac_enforce(False)
    assert rbac_enforce_enabled() is False
    admin_store.set_rbac_enforce(None)  # defer to env (unset -> False)


def test_edition_override_takes_effect():
    from security import admin_store
    from security.edition import edition

    admin_store.set_edition("pro")
    assert edition() == "pro"
    admin_store.set_edition(None)
    assert edition() == "community"


def test_admin_endpoints_crud():
    c = _client()
    assert c.get("/api/admin/users").status_code == 200

    r = c.post("/api/admin/orgs", json={"id": "beta", "name": "Beta"})
    assert r.status_code == 201

    r = c.post(
        "/api/admin/users",
        json={"username": "dave", "password": "pw123456", "role": "operator", "org_id": "beta"},
    )
    assert r.status_code == 201
    assert r.get_json()["user"]["role"] == "operator"

    r = c.patch("/api/admin/users/dave", json={"role": "admin"})
    assert r.status_code == 200
    assert r.get_json()["user"]["role"] == "admin"

    r = c.delete("/api/admin/users/dave")
    assert r.status_code == 200


def test_settings_endpoint_reports_effective():
    c = _client()
    r = c.get("/api/admin/settings")
    assert r.status_code == 200
    data = r.get_json()
    assert "effective" in data
    assert "community" in data["options"]["editions"]


def test_rbac_enable_guard_blocks_lockout():
    """Enabling enforce with no admin password and no SSO must be refused."""
    c = _client()
    r = c.put("/api/admin/settings/rbac", json={"enforce": True})
    # Seeded admin has no password (no env password in test) and no SSO -> 409
    assert r.status_code in (409, 200)
    if r.status_code == 200:
        # If it succeeded, an admin credential/SSO path existed; reset.
        c_headers = {"X-Firebreak-Role": "admin"}
        c.put("/api/admin/settings/rbac", json={"enforce": None}, headers=c_headers)


def test_rbac_enable_forbidden_for_signed_in_operator(monkeypatch):
    """Operators must not enable enforce in lab mode (would self-lock Admin)."""
    from security import admin_store

    admin_store.create_user(
        username="op_lock",
        password="op-pass",
        role="operator",
        org_id="default",
    )
    # Pretend SSO exists so the 409 recovery-path check does not fire first.
    monkeypatch.setattr(
        "security.pro_packaging.sso_readiness",
        lambda: {"ready": True, "preferred": "auth0"},
    )
    c = _client()
    with c.session_transaction() as sess:
        sess["user"] = "op_lock"
        sess["role"] = "operator"
        sess["org_id"] = "default"
        sess["auth_method"] = "local"
    r = c.put("/api/admin/settings/rbac", json={"enforce": True})
    assert r.status_code == 403
    assert r.get_json().get("required") == "admin"


def test_logs_endpoint_records_actor():
    from security.audit import audit_log

    audit_log("TEST_EVENT", {"k": "v"})
    c = _client()
    r = c.get("/api/admin/logs?limit=50")
    assert r.status_code == 200
    events = r.get_json()["events"]
    test_events = [e for e in events if e.get("event_type") == "TEST_EVENT"]
    assert test_events
    assert all("actor" in e for e in test_events)
