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
    from orchestrator.playbook_catalog import (
        list_playbooks,
        list_specialist_playbooks,
        playbook_for_posture,
    )

    posture = request.args.get("posture")
    rows = list_playbooks()
    return jsonify(
        {
            "count": len(rows),
            "playbooks": rows,
            "recommended": playbook_for_posture(posture) if posture else None,
            "default": DEFAULT_PLAYBOOK,
            "specialist": list_specialist_playbooks(),
        }
    )


@catalog_bp.get("/api/recon/methodology")
@require_role(Role.VIEWER)
def recon_methodology():
    from orchestrator.playbook_catalog import list_specialist_playbooks
    from tools.recon_methodology import FULL_WEB_RECON_TOOLS, RECON_PHASES, methodology_summary

    return jsonify(
        {
            "summary": methodology_summary(max_phases=len(RECON_PHASES)),
            "phases": RECON_PHASES,
            "full_tool_rotation": list(FULL_WEB_RECON_TOOLS),
            "specialist_playbooks": list_specialist_playbooks(),
        }
    )


@catalog_bp.get("/api/recon/dorks")
@require_role(Role.OPERATOR)
def recon_dorks():
    from tools.google_dorks import dorks_for_domain, sample_dorks

    domain = (request.args.get("domain") or "").strip()
    if not domain:
        return jsonify({"error": "domain query parameter is required"}), 400
    try:
        limit = int(request.args.get("limit") or "50")
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 500))
    include_catalog = request.args.get("catalog", "1").lower() not in {"0", "false", "no"}
    try:
        rows = dorks_for_domain(domain, include_catalog=include_catalog, catalog_limit=limit)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(
        {
            "domain": domain,
            "count": len(rows),
            "sample": sample_dorks(domain, count=min(12, limit)),
            "dorks": rows[:limit],
        }
    )


@catalog_bp.get("/api/recon/xss-payloads")
@require_role(Role.OPERATOR)
def recon_xss_payloads():
    from tools.xss_payloads import payloads_for_context

    context = request.args.get("context") or "html"
    rows = payloads_for_context(context)
    return jsonify({"context": context, "count": len(rows), "payloads": rows})


@catalog_bp.get("/api/tools")
@require_role(Role.VIEWER)
def tools_catalog():
    from orchestrator.mcp.registry import known_tools, list_scaffold_descriptors, list_tool_descriptors
    from orchestrator.ai.scaffold_tools import (
        EXPECTED_SCAFFOLD_COUNT,
        list_scaffold_tools,
        scaffold_tool_names,
    )
    from orchestrator.tasks import _TASK_MAP
    from tools.inventory import list_catalog

    wired = known_tools()
    catalog = list_catalog(
        category=request.args.get("category"),
        risk=request.args.get("risk"),
    )
    tools = [row for row in catalog if row["name"] in wired and not str(row["name"]).startswith("scaffold/")]
    scaffold_rows = list_scaffold_tools(limit=200)
    missing_wiring = sorted(
        name for name in wired if name not in {row["name"] for row in catalog} and not name.startswith("scaffold/")
    )
    return jsonify(
        {
            "count": len(tools),
            "wired_count": len(_TASK_MAP),
            "scaffold_count": len(scaffold_tool_names()),
            "note": (
                f"Firebreak ships {len(_TASK_MAP) - len(scaffold_tool_names())} CLI scanner wrappers "
                f"plus {EXPECTED_SCAFFOLD_COUNT} scaffold/* specialist bundle wrappers. "
                "Metasploit adds a large module library behind one tool; Nuclei uses template packs."
            ),
            "tools": tools,
            "scaffolds": scaffold_rows,
            "descriptors": list_tool_descriptors(request.args.get("category")),
            "scaffold_descriptors": list_scaffold_descriptors(),
            "unmapped_task_map": missing_wiring,
        }
    )


@catalog_bp.get("/api/methods")
@require_role(Role.VIEWER)
def attack_methods_catalog():
    from orchestrator.mcp.registry import known_tools
    from tools.attack_methods import (
        compile_aggressive_phases,
        list_methods,
        list_technique_families,
        methods_summary_for_llm,
    )

    posture = request.args.get("posture")
    allow = known_tools()
    methods = list_methods(posture=posture)
    for row in methods:
        row["tools"] = [t for t in row.get("tools") or [] if t in allow]
    return jsonify(
        {
            "count": len(methods),
            "posture": posture or "aggressive",
            "methods": methods,
            "technique_families": list_technique_families(),
            "summary": methods_summary_for_llm(posture=posture, allow=allow),
            "aggressive_phases": compile_aggressive_phases(allow),
        }
    )


@catalog_bp.get("/api/tools/custom")
@require_role(Role.VIEWER)
def custom_tools_list():
    from orchestrator.tools_registry import list_tools

    rows = list_tools(include_disabled=True)
    return jsonify({"count": len(rows), "tools": rows})


@catalog_bp.post("/api/tools/custom")
@require_role(Role.OPERATOR)
def custom_tools_register():
    """Approve + register a custom tool (the human clicking here is the approval gate)."""
    from flask import session

    from orchestrator.tools_registry import register_tool

    body = request.get_json(silent=True) or {}
    try:
        row = register_tool(
            body,
            created_by=session.get("user") or session.get("auth_method"),
            org_id=session.get("org_id"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        from security.audit import audit_log

        audit_log(
            "CUSTOM_TOOL_REGISTERED",
            {
                "name": row["name"],
                "binary": row["binary"],
                "risk": row["risk"],
                "by": row.get("created_by"),
            },
        )
    except Exception:
        pass
    return jsonify({"ok": True, "tool": row})


@catalog_bp.delete("/api/tools/custom/<name>")
@require_role(Role.OPERATOR)
def custom_tools_delete(name: str):
    from orchestrator.tools_registry import delete_tool

    removed = delete_tool(name)
    if not removed:
        return jsonify({"error": "not found", "name": name}), 404
    try:
        from security.audit import audit_log

        audit_log("CUSTOM_TOOL_DELETED", {"name": name})
    except Exception:
        pass
    return jsonify({"ok": True, "removed": name})


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
