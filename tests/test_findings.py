"""Normalized findings ingestion and API tests."""

from __future__ import annotations

import json

import pytest

from orchestrator.findings import (
    extract_findings_from_result,
    finding_fingerprint,
    findings_export_payload,
    ingest_result_rows,
    list_findings,
    render_findings_markdown,
    upsert_finding,
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_path = tmp_path / "findings.db"
    monkeypatch.setenv("FIREBREAK_DB_PATH", str(db_path))
    yield


def test_fingerprint_deduplicates_repeated_nuclei():
    fp1 = finding_fingerprint(
        target="lab.example",
        tool="nuclei",
        title="Exposed admin panel",
        endpoint="https://lab.example/admin",
        template_id="exposure-panel",
    )
    fp2 = finding_fingerprint(
        target="lab.example",
        tool="nuclei",
        title="Exposed admin panel",
        endpoint="https://lab.example/admin",
        template_id="exposure-panel",
    )
    assert fp1 == fp2


def test_ingest_deduplicates_same_fingerprint():
    rows = [
        {
            "id": 1,
            "target": "lab.example",
            "phase": "vuln_scan",
            "tool": "nuclei",
            "job_id": "job-1",
            "org_id": "default",
            "result": {
                "tool": "nuclei",
                "findings": [
                    {
                        "severity": "high",
                        "title": "Exposed admin panel",
                        "matched_at": "https://lab.example/admin",
                        "template_id": "exposure-panel",
                    }
                ],
            },
        },
        {
            "id": 2,
            "target": "lab.example",
            "phase": "vuln_scan",
            "tool": "nuclei",
            "job_id": "job-1",
            "org_id": "default",
            "result": {
                "tool": "nuclei",
                "findings": [
                    {
                        "severity": "high",
                        "title": "Exposed admin panel",
                        "matched_at": "https://lab.example/admin",
                        "template_id": "exposure-panel",
                    }
                ],
            },
        },
    ]
    stored = ingest_result_rows(rows)
    assert len(stored) == 2
    payload = list_findings(job_id="job-1", org_id="default")
    assert payload["total"] == 1
    assert payload["findings"][0]["observation_count"] == 2
    evidence = payload["findings"][0]["evidence"]
    assert len(evidence) == 2


def test_extract_sqlmap_and_ports():
    sql_rows = extract_findings_from_result(
        target="lab.example",
        phase="exploit",
        tool="sqlmap",
        result={"tool": "sqlmap", "vulnerable": True, "sqli": {"dbms": "mysql"}},
        job_id="job-2",
        org_id="default",
        result_id=9,
    )
    assert any("SQL injection" in row["title"] for row in sql_rows)

    port_rows = extract_findings_from_result(
        target="lab.example",
        phase="recon",
        tool="nmap",
        result={"tool": "nmap", "ports": [{"port": 443, "state": "open", "service": "https"}]},
        job_id="job-2",
        org_id="default",
        result_id=10,
    )
    assert any("443" in row["title"] for row in port_rows)


def test_export_empty_markdown():
    md = render_findings_markdown([], job_id="job-empty", target="lab.example")
    assert "No normalized findings" in md
    payload = findings_export_payload(job_id="job-empty", org_id="default")
    assert payload["count"] == 0
    assert "No normalized findings" in payload["markdown"]


def test_list_filters_severity():
    upsert_finding(
        {
            "fingerprint": "aaa",
            "target": "lab.example",
            "job_id": "job-3",
            "org_id": "default",
            "title": "Critical issue",
            "severity": "critical",
            "confidence": "high",
            "tool": "nuclei",
            "template_id": None,
            "endpoint": None,
            "first_seen": "2026-01-01T00:00:00+00:00",
            "last_seen": "2026-01-01T00:00:00+00:00",
            "observation_count": 1,
            "evidence": [{"result_id": 1, "phase": "scan", "tool": "nuclei", "available": True}],
        }
    )
    upsert_finding(
        {
            "fingerprint": "bbb",
            "target": "lab.example",
            "job_id": "job-3",
            "org_id": "default",
            "title": "Info note",
            "severity": "info",
            "confidence": "low",
            "tool": "nmap",
            "template_id": None,
            "endpoint": None,
            "first_seen": "2026-01-01T00:00:00+00:00",
            "last_seen": "2026-01-01T00:00:00+00:00",
            "observation_count": 1,
            "evidence": [{"result_id": 2, "phase": "scan", "tool": "nmap", "available": True}],
        }
    )
    payload = list_findings(job_id="job-3", org_id="default", severity="critical")
    assert payload["total"] == 1
    assert payload["findings"][0]["severity"] == "critical"


def _client():
    from orchestrator import dashboard

    return dashboard.app.test_client()


def test_findings_api_list_and_export():
    ingest_result_rows(
        [
            {
                "id": 11,
                "target": "lab.example",
                "phase": "scan",
                "tool": "nikto",
                "job_id": "job-api",
                "org_id": "default",
                "result": {"tool": "nikto", "issues": ["OSVDB-1234: /admin/ exposed"]},
            }
        ]
    )
    client = _client()
    resp = client.get("/api/findings?job_id=job-api")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] >= 1

    export = client.get("/api/missions/job-api/findings/export?format=json")
    assert export.status_code == 200
    body = export.get_json()
    assert body["count"] >= 1
    assert "findings" in body

    md_resp = client.get("/api/missions/job-api/findings/export?format=markdown")
    assert md_resp.status_code == 200
    assert b"Findings report" in md_resp.data
