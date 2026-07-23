"""Authorized-target management API."""

from __future__ import annotations

import json


def test_targets_api_crud(tmp_path, monkeypatch):
    path = tmp_path / "authorized_targets.json"
    path.write_text(json.dumps({"targets": []}), encoding="utf-8")
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))

    from orchestrator import dashboard

    client = dashboard.app.test_client()

    listed = client.get("/api/authorized-targets")
    assert listed.status_code == 200
    assert listed.get_json()["count"] == 0

    created = client.post(
        "/api/authorized-targets",
        json={"target": "https://www.wks.agency", "notes": "owner ok"},
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    body = created.get_json()
    assert body["target"]["target"] in {"wks.agency", "www.wks.agency"}

    listed = client.get("/api/authorized-targets")
    assert listed.get_json()["count"] == 1

    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    from scanner import AuthorizationEnforcer as A

    assert A.check("wks.agency") is True
    assert A.check("www.wks.agency") is True

    deleted = client.delete("/api/authorized-targets/wks.agency")
    assert deleted.status_code == 200
    assert client.get("/api/authorized-targets").get_json()["count"] == 0


def test_targets_default_to_output_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTHORIZED_TARGETS_FILE", raising=False)
    monkeypatch.setenv("FIREBREAK_OUTPUT_DIR", str(tmp_path / "output"))
    from scanner.authorization import targets_file_path

    assert targets_file_path() == tmp_path / "output" / "authorized_targets.json"
