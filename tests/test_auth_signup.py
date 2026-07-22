"""Self-service signup: creates an isolated org + operator and logs in."""

from __future__ import annotations

import uuid


def _client():
    from orchestrator import dashboard

    return dashboard.app.test_client()


def test_signup_creates_operator_and_authenticates():
    c = _client()
    username = f"user-{uuid.uuid4().hex[:8]}"

    r = c.post(
        "/auth/local/signup",
        json={"username": username, "password": "correcthorse", "org": "Acme Red Team"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    data = r.get_json()
    assert data["user"] == username
    assert data["role"] == "operator"
    assert data["org_id"]

    status = c.get("/auth/status").get_json()
    assert status["authenticated"] is True
    assert status["user"] == username


def test_signup_rejects_short_password():
    c = _client()
    r = c.post(
        "/auth/local/signup",
        json={"username": f"user-{uuid.uuid4().hex[:8]}", "password": "short"},
    )
    assert r.status_code == 400


def test_signup_rejects_duplicate_username():
    c = _client()
    username = f"user-{uuid.uuid4().hex[:8]}"
    body = {"username": username, "password": "correcthorse"}

    assert c.post("/auth/local/signup", json=body).status_code == 201
    dup = c.post("/auth/local/signup", json=body)
    assert dup.status_code == 409
