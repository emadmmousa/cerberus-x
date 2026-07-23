"""Dataset contribute / examples controllers."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, jsonify, request

from security.audit import audit_log
from security.rbac import Role, require_role

dataset_bp = Blueprint("dataset_api", __name__)


@dataset_bp.get("/api/dataset/examples")
@require_role(Role.VIEWER)
def api_dataset_examples():
    from orchestrator.dataset.pipeline import contribution_examples

    posture = (request.args.get("posture") or "").strip().lower() or None
    try:
        # Top 50 ready-made seed examples per posture (aggressive/defensive/balanced).
        seed_limit = max(0, min(int(request.args.get("limit") or 50), 50))
    except ValueError:
        seed_limit = 50
    rows = contribution_examples(posture=posture, seed_limit=seed_limit)
    return jsonify(
        {
            "count": len(rows),
            "posture": posture,
            "limit": seed_limit,
            "examples": rows,
            "license_default": "CC-BY-4.0",
            "guidance": (
                "Submit authorized Firebreak-shaped pairs only: planner JSON, "
                "hardening advice, or prompt-injection refuse. Filter by posture "
                "(aggressive / defensive / balanced) to load the top 50 ready-made "
                "seed examples for that type. No secrets, no unmanaged shell, "
                "no exploit PoCs for criminal misuse."
            ),
        }
    )


@dataset_bp.post("/api/dataset/contribute")
@require_role(Role.OPERATOR)
def api_dataset_contribute():
    from orchestrator.dataset.pipeline import accept_contribution

    body = request.get_json(silent=True) or {}
    try:
        rec = accept_contribution(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    out_dir = Path(
        os.environ.get("FIREBREAK_OUTPUT_DIR")
        or (Path(__file__).resolve().parents[3] / "output")
    )
    out_path = out_dir / "dataset" / "contributions.jsonl"
    repo_mirror = (
        Path(__file__).resolve().parents[3]
        / "training"
        / "dataset"
        / "v0"
        / "contributions.jsonl"
    )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("a", encoding="utf-8") as fh:
            import json as _json

            fh.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        persisted = True
        warning = None
        try:
            if repo_mirror.parent.is_dir():
                with repo_mirror.open("a", encoding="utf-8") as fh:
                    import json as _json

                    fh.write(_json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass
    except OSError as exc:
        persisted = False
        warning = str(exc)
    audit_log(
        "DATASET_CONTRIBUTE",
        {
            "id": rec.get("id"),
            "license": rec.get("license"),
            "posture": rec.get("posture"),
            "persisted": persisted,
            "prompt_preview": str(rec.get("prompt") or "")[:160],
        },
    )
    payload = {"accepted": True, "persisted": persisted, "record": rec}
    if warning:
        payload["warning"] = warning
    return jsonify(payload)
