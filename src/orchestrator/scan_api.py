"""Active scan job API (threaded lightweight probes)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from scanner import AuthorizationEnforcer, VulnerabilityScanner
from security.audit import audit_log

scan_bp = Blueprint("scan", __name__)
scan_jobs: dict[str, dict] = {}


def _run_scan(job_id: str, target: str, use_proxy: bool, proxy_protocol: str, evasion: dict):
    scan_jobs[job_id]["state"] = "RUNNING"
    try:
        scanner = VulnerabilityScanner(target, use_proxy, proxy_protocol, evasion)
        findings = scanner.scan_all()
        scan_jobs[job_id]["findings"] = findings
        scan_jobs[job_id]["state"] = "COMPLETE"
        audit_log(
            "SCAN_COMPLETE",
            {"job_id": job_id, "target": target, "findings": len(findings)},
        )
    except Exception as exc:
        scan_jobs[job_id]["state"] = "FAILED"
        scan_jobs[job_id]["error"] = str(exc)
        audit_log(
            "SCAN_FAILED",
            {"job_id": job_id, "target": target, "error": str(exc)},
            severity="high",
        )


@scan_bp.route("/scan/start", methods=["POST"])
def start_scan():
    data = request.get_json(silent=True) or {}
    target = data.get("target")
    if not target:
        return jsonify({"error": "target required"}), 400
    if not AuthorizationEnforcer.check(target):
        return jsonify({"error": "Unauthorized target"}), 403

    use_proxy = bool(data.get("use_proxy", False))
    proxy_protocol = data.get("proxy_protocol") or "http"
    evasion = data.get("evasion") or {}
    if not isinstance(evasion, dict):
        evasion = {}

    job_id = str(uuid.uuid4())
    scan_jobs[job_id] = {
        "job_id": job_id,
        "target": target,
        "state": "PENDING",
        "started": datetime.now(timezone.utc).isoformat(),
        "findings": [],
    }
    threading.Thread(
        target=_run_scan,
        args=(job_id, target, use_proxy, proxy_protocol, evasion),
        daemon=True,
    ).start()
    audit_log("SCAN_STARTED", {"job_id": job_id, "target": target})
    return jsonify({"job_id": job_id, "status": "started"})


@scan_bp.route("/scan/status/<job_id>", methods=["GET"])
def scan_status(job_id: str):
    job = scan_jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)
