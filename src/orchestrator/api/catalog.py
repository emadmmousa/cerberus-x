"""Playbook / tools catalog controllers."""

from __future__ import annotations

import os

import yaml
from flask import Blueprint, jsonify, request

from security.rbac import Role, require_role

catalog_bp = Blueprint("catalog_api", __name__)

DEFAULT_PLAYBOOK = os.environ.get(
    "PLAYBOOK_PATH", "playbooks/complete_dark_arsenal.yaml"
)


@catalog_bp.get("/api/playbook")
@require_role(Role.VIEWER)
def playbook_summary():
    playbook_path = request.args.get("playbook", DEFAULT_PLAYBOOK)
    try:
        with open(playbook_path) as handle:
            playbook = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return jsonify({"error": f"playbook not found: {playbook_path}"}), 404

    phases = []
    for phase in playbook.get("phases", []):
        phases.append(
            {
                "name": phase.get("name"),
                "tools": [t.get("tool") for t in phase.get("tools", []) if t.get("tool")],
                "parallel": bool(phase.get("parallel", False)),
                "depends_on": phase.get("depends_on", []),
                "when": phase.get("when"),
            }
        )
    return jsonify(
        {
            "name": playbook.get("name"),
            "path": playbook_path,
            "evasion": playbook.get("evasion"),
            "phases": phases,
        }
    )


@catalog_bp.get("/api/playbooks")
@require_role(Role.VIEWER)
def playbooks_catalog():
    from orchestrator.playbook_catalog import list_playbooks, playbook_for_posture

    posture = request.args.get("posture")
    rows = list_playbooks()
    return jsonify(
        {
            "count": len(rows),
            "playbooks": rows,
            "recommended": playbook_for_posture(posture) if posture else None,
            "default": DEFAULT_PLAYBOOK,
        }
    )


@catalog_bp.get("/api/tools")
@require_role(Role.VIEWER)
def tools_catalog():
    from orchestrator.mcp.registry import known_tools, list_tool_descriptors
    from tools.inventory import list_catalog

    wired = known_tools()
    catalog = list_catalog(
        category=request.args.get("category"),
        risk=request.args.get("risk"),
    )
    tools = [row for row in catalog if row["name"] in wired]
    missing_wiring = sorted(wired - {row["name"] for row in catalog})
    return jsonify(
        {
            "count": len(tools),
            "wired_count": len(wired),
            "note": (
                "Firebreak ships 23 scanner wrappers. Metasploit adds a large module "
                "library behind the single 'metasploit' tool; Nuclei uses template packs."
            ),
            "tools": tools,
            "descriptors": list_tool_descriptors(request.args.get("category")),
            "unmapped_task_map": missing_wiring,
        }
    )


@catalog_bp.get("/api/tools/health")
@require_role(Role.OPERATOR)
def tools_health():
    from celery.result import AsyncResult

    from orchestrator.celery_app import app as celery_app
    from orchestrator.tasks import run_tools_health_task

    task_id = request.args.get("task_id")
    if task_id:
        result = AsyncResult(task_id, app=celery_app)
        payload = {
            "task_id": task_id,
            "state": result.state,
        }
        if result.state == "SUCCESS":
            payload["result"] = result.result
        elif result.state == "FAILURE":
            payload["error"] = str(result.result)
        return jsonify(payload)

    async_result = run_tools_health_task.delay()
    return jsonify({"task_id": async_result.id, "state": async_result.state})
