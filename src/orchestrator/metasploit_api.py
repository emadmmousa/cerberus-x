"""Flask routes for the server-side Metasploit RPC integration."""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from typing import Any

from flask import Blueprint, jsonify, request

from tools.metasploit_rpc import MetasploitRpcClient, MetasploitRpcError


ClientFactory = Callable[[], MetasploitRpcClient]

MODULE_TYPES = {
    "auxiliary",
    "encoder",
    "evasion",
    "exploit",
    "nop",
    "payload",
    "post",
}
MODULE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")
SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "pass",
    "pwd",
    "token",
    "secret",
    "credential",
    "userpass",
    "smbpass",
    "private_key",
    "priv_key",
)


class ApiError(Exception):
    """An expected API error with a stable response code."""

    def __init__(self, message: str, code: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _safe_json(value: Any) -> Any:
    """Remove credentials from RPC data before it reaches a browser."""
    if isinstance(value, Mapping):
        return {
            str(key): _safe_json(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_json(item) for item in value]
    return value


def _safe_error_message(error: Exception) -> str:
    message = str(error) or "Metasploit RPC is unavailable"
    password = os.getenv("MSF_RPC_PASSWORD")
    if password:
        message = message.replace(password, "[REDACTED]")
    return message


def _error_response(error: str, code: str, status: int):
    return jsonify({"error": error, "code": code}), status


def _validate_module(module_type: Any, module_name: Any) -> tuple[str, str]:
    if not isinstance(module_type, str) or not isinstance(module_name, str):
        raise ApiError(
            "Module type and name are required",
            "invalid_input",
        )

    normalized_type = module_type.strip().lower()
    normalized_name = module_name.strip()
    if normalized_type not in MODULE_TYPES:
        raise ApiError(
            f"Unsupported Metasploit module type: {module_type}",
            "invalid_module_type",
        )
    path_parts = normalized_name.split("/")
    if (
        not normalized_name
        or not MODULE_NAME_PATTERN.fullmatch(normalized_name)
        or any(part in {".", ".."} for part in path_parts)
    ):
        raise ApiError("Invalid Metasploit module name", "invalid_input")
    return normalized_type, normalized_name


def _json_body() -> dict[str, Any]:
    if not request.is_json:
        raise ApiError("A JSON request body is required", "invalid_json")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError("A JSON object request body is required", "invalid_json")
    return body


def _validate_options(
    definitions: Any, supplied_options: Any
) -> dict[str, Any]:
    if not isinstance(supplied_options, dict):
        raise ApiError("Module options must be a JSON object", "invalid_options")
    if not isinstance(definitions, dict):
        raise MetasploitRpcError(
            "Metasploit RPC returned invalid module options"
        )

    options: dict[str, Any] = {}
    for key, value in supplied_options.items():
        if not isinstance(key, str) or not key.strip():
            raise ApiError(
                "Module option names must be non-empty strings",
                "invalid_options",
            )
        normalized_key = key.strip().upper()
        if normalized_key not in definitions:
            raise ApiError(
                f"Unknown module option: {normalized_key}",
                "invalid_options",
            )
        options[normalized_key] = value

    missing = []
    for name, metadata in definitions.items():
        if not isinstance(metadata, dict) or metadata.get("required") is not True:
            continue
        supplied = name in options and options[name] not in ("", None)
        has_default = metadata.get("default") not in ("", None)
        if not supplied and not has_default:
            missing.append(name)
    if missing:
        raise ApiError(
            f"Missing required module options: {', '.join(sorted(missing))}",
            "missing_required_options",
        )
    return options


def _contains_identifier(collection: Any, identifier: str) -> bool:
    if isinstance(collection, Mapping):
        return identifier in {str(key) for key in collection}
    return False


def _session(collection: Any, session_id: str) -> Mapping[str, Any] | None:
    if not isinstance(collection, Mapping):
        return None
    for key, value in collection.items():
        if str(key) == session_id and isinstance(value, Mapping):
            return value
    return None


def create_metasploit_blueprint(
    client_factory: ClientFactory = MetasploitRpcClient,
) -> Blueprint:
    """Create the Metasploit API blueprint with an injectable RPC client."""
    blueprint = Blueprint(
        "metasploit",
        __name__,
        url_prefix="/api/metasploit",
    )

    @blueprint.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return _error_response(error.message, error.code, error.status)

    @blueprint.errorhandler(MetasploitRpcError)
    def handle_rpc_error(error: MetasploitRpcError):
        return _error_response(
            _safe_error_message(error),
            "metasploit_unavailable",
            503,
        )

    @blueprint.get("/health")
    def health():
        rpc_status = client_factory().call("core.version")
        return jsonify({"status": "ok", "rpc": _safe_json(rpc_status)})

    @blueprint.get("/modules")
    def search_modules():
        query = request.args.get("q", "")
        module_type = request.args.get("type")
        if module_type:
            module_type, _ = _validate_module(
                module_type, "placeholder"
            )
        modules = client_factory().search_modules(
            query, module_type=module_type
        )
        return jsonify({"modules": _safe_json(modules)})

    @blueprint.get("/modules/<module_type>/<path:module_name>")
    def module_detail(module_type: str, module_name: str):
        module_type, module_name = _validate_module(module_type, module_name)
        client = client_factory()
        info = client.module_info(module_type, module_name)
        options = client.module_options(module_type, module_name)
        return jsonify(
            {
                "module": _safe_json(info),
                "options": _safe_json(options),
            }
        )

    @blueprint.post("/modules/run")
    def run_module():
        body = _json_body()
        module_type, module_name = _validate_module(
            body.get("type"), body.get("name")
        )
        if "options" not in body:
            raise ApiError(
                "Module options must be provided",
                "invalid_options",
            )
        if not isinstance(body["options"], dict):
            raise ApiError(
                "Module options must be a JSON object",
                "invalid_options",
            )

        client = client_factory()
        definitions = client.module_options(module_type, module_name)
        options = _validate_options(definitions, body["options"])
        result = client.execute_module(module_type, module_name, options)
        return jsonify(
            {
                "module": f"{module_type}/{module_name}",
                "result": _safe_json(result),
            }
        )

    @blueprint.get("/jobs")
    def list_jobs():
        jobs = client_factory().list_jobs()
        return jsonify({"jobs": _safe_json(jobs)})

    @blueprint.delete("/jobs/<job_id>")
    def stop_job(job_id: str):
        client = client_factory()
        jobs = client.list_jobs()
        if not _contains_identifier(jobs, job_id):
            raise ApiError(
                f"Metasploit job {job_id} was not found",
                "job_not_found",
                404,
            )
        result = client.stop_job(job_id)
        return jsonify({"job_id": job_id, "result": _safe_json(result)})

    @blueprint.get("/sessions")
    def list_sessions():
        sessions = client_factory().list_sessions()
        return jsonify({"sessions": _safe_json(sessions)})

    @blueprint.post("/sessions/<session_id>/command")
    def run_session_command(session_id: str):
        body = _json_body()
        command = body.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ApiError(
                "A non-empty session command is required",
                "invalid_input",
            )

        client = client_factory()
        session = _session(client.list_sessions(), session_id)
        if session is None:
            raise ApiError(
                f"Metasploit session {session_id} was not found",
                "session_not_found",
                404,
            )
        session_type = str(session.get("type", "shell")).lower()
        if session_type not in {"shell", "meterpreter"}:
            raise ApiError(
                f"Unsupported Metasploit session type: {session_type}",
                "invalid_session_type",
            )
        payload = command if command.endswith("\n") else f"{command}\n"
        if session_type == "meterpreter":
            payload = command
        result = client.write_session(
            session_id,
            payload,
            session_type=session_type,
        )
        return jsonify(
            {"session_id": session_id, "result": _safe_json(result)}
        )

    @blueprint.delete("/sessions/<session_id>")
    def stop_session(session_id: str):
        client = client_factory()
        sessions = client.list_sessions()
        if not _contains_identifier(sessions, session_id):
            raise ApiError(
                f"Metasploit session {session_id} was not found",
                "session_not_found",
                404,
            )
        result = client.stop_session(session_id)
        return jsonify({"session_id": session_id, "result": _safe_json(result)})

    return blueprint


msf_bp = create_metasploit_blueprint()
# Backward-compatible export for existing integrations.
metasploit_blueprint = msf_bp
