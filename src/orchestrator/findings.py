"""Normalized findings ingestion, storage, and export."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from orchestrator.database import get_db, init_db

_SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
    "unknown": 5,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def normalize_severity(raw: str | None) -> str:
    token = _norm(raw)
    if token in _SEVERITY_RANK:
        return token
    if token in {"crit", "severe"}:
        return "critical"
    if token in {"warn", "warning"}:
        return "medium"
    return "info"


def finding_fingerprint(
    *,
    target: str,
    tool: str | None,
    title: str,
    endpoint: str | None = None,
    template_id: str | None = None,
) -> str:
    parts = "|".join(
        [
            _norm(target),
            _norm(tool),
            _norm(title),
            _norm(endpoint),
            _norm(template_id),
        ]
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:32]


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    nested = result.get("result")
    if isinstance(nested, dict):
        return nested
    return result


def _row(
    *,
    target: str,
    phase: str,
    tool: str | None,
    title: str,
    severity: str,
    confidence: str,
    endpoint: str | None,
    template_id: str | None,
    job_id: str | None,
    org_id: str | None,
    result_id: int | None,
    timestamp: str | None,
) -> dict[str, Any]:
    fp = finding_fingerprint(
        target=target,
        tool=tool,
        title=title,
        endpoint=endpoint,
        template_id=template_id,
    )
    evidence = [
        {
            "result_id": result_id,
            "phase": phase,
            "tool": tool,
            "timestamp": timestamp or _utc_now(),
            "available": result_id is not None,
        }
    ]
    return {
        "fingerprint": fp,
        "target": target,
        "job_id": job_id,
        "org_id": org_id,
        "title": title.strip() or "Finding",
        "severity": normalize_severity(severity),
        "confidence": confidence,
        "tool": tool,
        "template_id": template_id,
        "endpoint": endpoint,
        "first_seen": timestamp or _utc_now(),
        "last_seen": timestamp or _utc_now(),
        "observation_count": 1,
        "evidence": evidence,
    }


def extract_findings_from_result(
    *,
    target: str,
    phase: str,
    tool: str | None,
    result: dict[str, Any],
    job_id: str | None = None,
    org_id: str | None = None,
    result_id: int | None = None,
    timestamp: str | None = None,
) -> list[dict[str, Any]]:
    """Derive normalized finding rows from one tool result payload."""
    payload = _payload(result)
    tool_name = tool or str(payload.get("tool") or "unknown")
    rows: list[dict[str, Any]] = []

    if payload.get("skipped"):
        return rows

    findings = payload.get("findings")
    if isinstance(findings, list):
        for item in findings:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("name") or "Template match")
                endpoint = (
                    item.get("matched_at")
                    or item.get("url")
                    or item.get("host")
                    or item.get("endpoint")
                )
                rows.append(
                    _row(
                        target=target,
                        phase=phase,
                        tool=tool_name,
                        title=title,
                        severity=str(item.get("severity") or "medium"),
                        confidence=str(item.get("confidence") or "medium"),
                        endpoint=str(endpoint) if endpoint else None,
                        template_id=str(item.get("template_id") or item.get("template-id") or "")
                        or None,
                        job_id=job_id,
                        org_id=org_id,
                        result_id=result_id,
                        timestamp=timestamp,
                    )
                )
            elif isinstance(item, str) and item.strip():
                rows.append(
                    _row(
                        target=target,
                        phase=phase,
                        tool=tool_name,
                        title=item.strip()[:240],
                        severity="medium",
                        confidence="medium",
                        endpoint=None,
                        template_id=None,
                        job_id=job_id,
                        org_id=org_id,
                        result_id=result_id,
                        timestamp=timestamp,
                    )
                )

    issues = payload.get("issues")
    if isinstance(issues, list):
        for issue in issues[:50]:
            if not issue:
                continue
            title = str(issue).strip()[:240]
            rows.append(
                _row(
                    target=target,
                    phase=phase,
                    tool=tool_name,
                    title=title,
                    severity="medium",
                    confidence="medium",
                    endpoint=None,
                    template_id=None,
                    job_id=job_id,
                    org_id=org_id,
                    result_id=result_id,
                    timestamp=timestamp,
                )
            )

    ports = payload.get("ports")
    if isinstance(ports, list):
        for port_row in ports[:100]:
            if not isinstance(port_row, dict):
                continue
            port = port_row.get("port")
            state = str(port_row.get("state") or "open").lower()
            if state not in {"open", "open|filtered"}:
                continue
            service = port_row.get("service") or port_row.get("name") or "unknown"
            endpoint = f"{target}:{port}"
            rows.append(
                _row(
                    target=target,
                    phase=phase,
                    tool=tool_name,
                    title=f"Open port {port}/{service}",
                    severity="info",
                    confidence="high",
                    endpoint=endpoint,
                    template_id=None,
                    job_id=job_id,
                    org_id=org_id,
                    result_id=result_id,
                    timestamp=timestamp,
                )
            )

    if tool_name == "sqlmap" and payload.get("vulnerable"):
        dbms = (payload.get("sqli") or {}).get("dbms") if isinstance(payload.get("sqli"), dict) else None
        title = "SQL injection confirmed"
        if dbms:
            title = f"SQL injection confirmed ({dbms})"
        rows.append(
            _row(
                target=target,
                phase=phase,
                tool=tool_name,
                title=title,
                severity="high",
                confidence="high",
                endpoint=str(payload.get("url") or target),
                template_id=None,
                job_id=job_id,
                org_id=org_id,
                result_id=result_id,
                timestamp=timestamp,
            )
        )

    if tool_name == "metasploit":
        if payload.get("vulnerable"):
            module = payload.get("module") or "exploit module"
            rows.append(
                _row(
                    target=target,
                    phase=phase,
                    tool=tool_name,
                    title=f"Exploit succeeded ({module})",
                    severity="critical",
                    confidence="high",
                    endpoint=str(payload.get("target") or target),
                    template_id=str(module),
                    job_id=job_id,
                    org_id=org_id,
                    result_id=result_id,
                    timestamp=timestamp,
                )
            )
        sessions = payload.get("sessions")
        if isinstance(sessions, list) and sessions:
            rows.append(
                _row(
                    target=target,
                    phase=phase,
                    tool=tool_name,
                    title=f"Meterpreter/session established ({len(sessions)})",
                    severity="critical",
                    confidence="high",
                    endpoint=str(payload.get("target") or target),
                    template_id=None,
                    job_id=job_id,
                    org_id=org_id,
                    result_id=result_id,
                    timestamp=timestamp,
                )
            )

    ffuf_results = payload.get("results")
    if tool_name == "ffuf" and isinstance(ffuf_results, list):
        for hit in ffuf_results[:25]:
            if not isinstance(hit, dict):
                continue
            url = hit.get("url") or hit.get("input") or hit.get("path")
            status = hit.get("status") or hit.get("status_code")
            if not url:
                continue
            rows.append(
                _row(
                    target=target,
                    phase=phase,
                    tool=tool_name,
                    title=f"Fuzz hit ({status}) {url}",
                    severity="low",
                    confidence="medium",
                    endpoint=str(url),
                    template_id=None,
                    job_id=job_id,
                    org_id=org_id,
                    result_id=result_id,
                    timestamp=timestamp,
                )
            )

    if payload.get("error") and not rows:
        err = str(payload.get("error")).strip()
        if err and not payload.get("partial"):
            rows.append(
                _row(
                    target=target,
                    phase=phase,
                    tool=tool_name,
                    title=f"Tool error: {err[:180]}",
                    severity="info",
                    confidence="low",
                    endpoint=None,
                    template_id=None,
                    job_id=job_id,
                    org_id=org_id,
                    result_id=result_id,
                    timestamp=timestamp,
                )
            )

    return rows


def _ensure_findings_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint TEXT NOT NULL UNIQUE,
            target TEXT NOT NULL,
            job_id TEXT,
            org_id TEXT DEFAULT 'default',
            title TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            confidence TEXT DEFAULT 'medium',
            tool TEXT,
            template_id TEXT,
            endpoint TEXT,
            first_seen TEXT,
            last_seen TEXT,
            observation_count INTEGER DEFAULT 1,
            evidence_json TEXT
        )
        """
    )


def upsert_finding(row: dict[str, Any]) -> dict[str, Any]:
    init_db()
    with get_db() as conn:
        _ensure_findings_table(conn)
        existing = conn.execute(
            "SELECT id, evidence_json, observation_count, first_seen FROM findings WHERE fingerprint = ?",
            (row["fingerprint"],),
        ).fetchone()
        evidence = row.get("evidence") or []
        if existing:
            fid, evidence_json, count, first_seen = existing
            merged = json.loads(evidence_json or "[]")
            seen_ids = {item.get("result_id") for item in merged if isinstance(item, dict)}
            for item in evidence:
                rid = item.get("result_id")
                if rid not in seen_ids:
                    merged.append(item)
                    seen_ids.add(rid)
            conn.execute(
                """
                UPDATE findings SET
                    last_seen = ?,
                    observation_count = ?,
                    severity = ?,
                    confidence = ?,
                    evidence_json = ?
                WHERE id = ?
                """,
                (
                    row.get("last_seen") or _utc_now(),
                    int(count or 1) + 1,
                    row.get("severity") or "info",
                    row.get("confidence") or "medium",
                    json.dumps(merged),
                    fid,
                ),
            )
            conn.commit()
            return get_finding_by_id(int(fid))

        conn.execute(
            """
            INSERT INTO findings (
                fingerprint, target, job_id, org_id, title, severity, confidence,
                tool, template_id, endpoint, first_seen, last_seen,
                observation_count, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["fingerprint"],
                row["target"],
                row.get("job_id"),
                row.get("org_id") or "default",
                row["title"],
                row.get("severity") or "info",
                row.get("confidence") or "medium",
                row.get("tool"),
                row.get("template_id"),
                row.get("endpoint"),
                row.get("first_seen") or _utc_now(),
                row.get("last_seen") or _utc_now(),
                row.get("observation_count") or 1,
                json.dumps(evidence),
            ),
        )
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return get_finding_by_id(int(new_id))


def ingest_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stored: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        extracted = extract_findings_from_result(
            target=str(raw.get("target") or ""),
            phase=str(raw.get("phase") or ""),
            tool=raw.get("tool"),
            result=raw.get("result") if isinstance(raw.get("result"), dict) else raw,
            job_id=raw.get("job_id"),
            org_id=raw.get("org_id"),
            result_id=raw.get("id"),
            timestamp=raw.get("timestamp"),
        )
        for item in extracted:
            stored.append(upsert_finding(item))
    return stored


def _serialize_finding(row: tuple) -> dict[str, Any]:
    evidence = json.loads(row[13] or "[]") if len(row) > 13 else []
    return {
        "id": row[0],
        "fingerprint": row[1],
        "target": row[2],
        "job_id": row[3],
        "org_id": row[4],
        "title": row[5],
        "severity": row[6],
        "confidence": row[7],
        "tool": row[8],
        "template_id": row[9],
        "endpoint": row[10],
        "first_seen": row[11],
        "last_seen": row[12],
        "observation_count": row[14] if len(row) > 14 else 1,
        "evidence": evidence,
    }


def get_finding_by_id(finding_id: int) -> dict[str, Any]:
    init_db()
    with get_db() as conn:
        _ensure_findings_table(conn)
        row = conn.execute(
            """
            SELECT id, fingerprint, target, job_id, org_id, title, severity, confidence,
                   tool, template_id, endpoint, first_seen, last_seen, evidence_json,
                   observation_count
            FROM findings WHERE id = ?
            """,
            (finding_id,),
        ).fetchone()
        if not row:
            raise KeyError(finding_id)
        return _serialize_finding(row)


def list_findings(
    *,
    org_id: str | None = None,
    job_id: str | None = None,
    target: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    if org_id:
        clauses.append("(org_id = ? OR org_id IS NULL)")
        params.append(org_id)
    if job_id:
        clauses.append("job_id = ?")
        params.append(job_id)
    if target:
        clauses.append("target = ?")
        params.append(target)
    if severity:
        clauses.append("severity = ?")
        params.append(normalize_severity(severity))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_db() as conn:
        _ensure_findings_table(conn)
        total = conn.execute(
            f"SELECT COUNT(*) FROM findings {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT id, fingerprint, target, job_id, org_id, title, severity, confidence,
                   tool, template_id, endpoint, first_seen, last_seen, evidence_json,
                   observation_count
            FROM findings {where}
            ORDER BY last_seen DESC
            LIMIT ? OFFSET ?
            """,
            [*params, max(1, min(limit, 500)), max(0, offset)],
        ).fetchall()
    findings = [_serialize_finding(row) for row in rows]
    findings.sort(
        key=lambda item: (
            _SEVERITY_RANK.get(str(item.get("severity")).lower(), 99),
            item.get("last_seen") or "",
        )
    )
    return {
        "count": len(findings),
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "findings": findings,
    }


def findings_export_payload(
    *,
    job_id: str,
    target: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    data = list_findings(org_id=org_id, job_id=job_id, target=target, limit=500, offset=0)
    rows = data["findings"]
    return {
        "job_id": job_id,
        "target": target or (rows[0]["target"] if rows else None),
        "count": len(rows),
        "summary": (
            f"{len(rows)} normalized finding(s) for mission {job_id}."
            if rows
            else f"No normalized findings recorded for mission {job_id}."
        ),
        "findings": rows,
        "markdown": render_findings_markdown(rows, job_id=job_id, target=target),
    }


def render_findings_markdown(
    findings: list[dict[str, Any]],
    *,
    job_id: str | None = None,
    target: str | None = None,
) -> str:
    title_target = target or (findings[0]["target"] if findings else "unknown")
    lines = [
        f"# Findings report — {title_target}",
        "",
    ]
    if job_id:
        lines.append(f"- Mission: `{job_id}`")
    lines.extend(["", "## Summary", ""])
    if not findings:
        lines.append("_No normalized findings recorded for this mission._")
        lines.append("")
        lines.append(
            "Raw tool output may still be available in phase results; evidence was not "
            "promoted to the findings store."
        )
        return "\n".join(lines) + "\n"

    lines.append(f"- Total findings: **{len(findings)}**")
    by_sev: dict[str, int] = {}
    for row in findings:
        sev = normalize_severity(row.get("severity"))
        by_sev[sev] = by_sev.get(sev, 0) + 1
    for sev in sorted(by_sev, key=lambda s: _SEVERITY_RANK.get(s, 99)):
        lines.append(f"- {sev}: {by_sev[sev]}")
    lines.extend(["", "## Findings", ""])
    for idx, row in enumerate(findings, 1):
        sev = row.get("severity") or "info"
        lines.append(f"{idx}. **{row.get('title', 'Finding')}** ({sev})")
        if row.get("tool"):
            lines.append(f"   - Tool: `{row['tool']}`")
        if row.get("endpoint"):
            lines.append(f"   - Endpoint: `{row['endpoint']}`")
        if row.get("template_id"):
            lines.append(f"   - Template: `{row['template_id']}`")
        lines.append(f"   - Observations: {row.get('observation_count', 1)}")
        evidence = row.get("evidence") or []
        if evidence:
            sample = evidence[-1]
            if sample.get("available"):
                lines.append(
                    f"   - Evidence: phase `{sample.get('phase')}` result `{sample.get('result_id')}`"
                )
            else:
                lines.append("   - Evidence: _unavailable_")
        lines.append("")
    return "\n".join(lines)
