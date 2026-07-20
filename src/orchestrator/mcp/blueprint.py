"""Flask MCP JSON-RPC + SSE endpoints."""

from __future__ import annotations

import json
import time

from flask import Blueprint, Response, jsonify, request, stream_with_context

from orchestrator.mcp import actions, auth, sessions
from orchestrator.mcp.registry import list_tool_descriptors

mcp_bp = Blueprint("mcp", __name__)


def _ok(result, req_id=None):
    return jsonify({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(code: int, message: str, req_id=None, http_status: int = 400):
    return (
        jsonify(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": code, "message": message},
            }
        ),
        http_status,
    )


def _call_tool(name: str, arguments: dict):
    arguments = arguments or {}
    if name == "session_create":
        target = arguments.get("target") or ""
        if not str(target).strip():
            raise ValueError("target is required")
        return sessions.create_session(str(target), arguments.get("label"))

    session_id = arguments.get("session_id")
    if name != "list_tools" and not session_id and name not in {"session_create"}:
        # list_tools also requires session for audit consistency
        pass

    if name == "list_tools":
        if not session_id or not sessions.get_session(session_id):
            raise PermissionError("session_id required")
        tools = list_tool_descriptors(arguments.get("category"))
        sessions.audit(session_id, {"action": "list_tools", "count": len(tools)})
        return {"tools": tools}

    if name == "run_tool":
        return actions.enqueue_tool(
            session_id=session_id,
            tool=arguments.get("tool"),
            target=arguments.get("target"),
            args=arguments.get("args"),
            use_proxy=bool(arguments.get("use_proxy", False)),
            proxy_protocol=arguments.get("proxy_protocol") or "http",
            evasion=arguments.get("evasion")
            if isinstance(arguments.get("evasion"), dict)
            else {},
            confirm=bool(arguments.get("confirm", False)),
        )

    if name == "get_job_status":
        return actions.task_status(session_id, arguments.get("task_id") or "")

    if name == "get_findings":
        return {
            "findings": actions.findings(
                session_id,
                arguments.get("target") or "",
                job_id=arguments.get("job_id"),
                tool=arguments.get("tool"),
                phase=arguments.get("phase"),
                limit=int(arguments.get("limit") or 100),
            )
        }

    if name == "list_sessions":
        # privileged listing still needs API key (already checked)
        return {"sessions": sessions.list_sessions(int(arguments.get("limit") or 20))}

    if name == "suggest_next_phase":
        from orchestrator.ai import planner

        if not session_id or not sessions.get_session(session_id):
            raise PermissionError("session_id required")
        plan = planner.suggest_next_phase(
            arguments.get("target") or sessions.get_session(session_id)["target"],
            arguments.get("results")
            if isinstance(arguments.get("results"), dict)
            else {},
            nl_goal=arguments.get("nl_goal") or "",
            step=int(arguments.get("step") or 0),
        )
        sessions.audit(session_id, {"action": "suggest_next_phase", "plan": plan})
        return plan

    raise ValueError(f"unknown tool: {name}")


@mcp_bp.route("/mcp", methods=["POST"])
def mcp_jsonrpc():
    denied = auth.require_api_key(request)
    if denied is not None:
        return denied

    body = request.get_json(silent=True) or {}
    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}

    try:
        if method == "tools/list":
            # MCP-style list without session uses empty — require session via params
            session_id = params.get("session_id")
            if session_id:
                if not sessions.get_session(session_id):
                    return _err(-32001, "invalid session_id", req_id, 403)
                tools = list_tool_descriptors(params.get("category"))
                sessions.audit(session_id, {"action": "tools/list", "count": len(tools)})
            else:
                tools = list_tool_descriptors(params.get("category"))
            return _ok({"tools": tools}, req_id)

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            result = _call_tool(name, arguments)
            return _ok(result, req_id)

        if method == "initialize":
            return _ok(
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cerberus-x", "version": "1.0.0"},
                },
                req_id,
            )

        return _err(-32601, f"method not found: {method}", req_id, 404)
    except PermissionError as exc:
        return _err(-32001, str(exc), req_id, 403)
    except ValueError as exc:
        return _err(-32602, str(exc), req_id, 400)
    except RuntimeError as exc:
        return _err(-32000, str(exc), req_id, 429)
    except Exception as exc:
        return _err(-32603, str(exc), req_id, 500)


@mcp_bp.route("/mcp/sse", methods=["GET"])
def mcp_sse():
    denied = auth.require_api_key(request)
    if denied is not None:
        return denied

    @stream_with_context
    def generate():
        yield "event: ready\ndata: {\"ok\": true}\n\n"
        for _ in range(30):
            yield f"event: ping\ndata: {json.dumps({'ts': time.time()})}\n\n"
            time.sleep(1)

    return Response(generate(), mimetype="text/event-stream")
