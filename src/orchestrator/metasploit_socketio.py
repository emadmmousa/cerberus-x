"""Socket.IO handlers for SID-scoped Metasploit RPC consoles."""

from __future__ import annotations

import os
import threading
from collections.abc import Callable, Mapping
from typing import Any

from flask import request
from flask_socketio import SocketIO

from tools.metasploit_rpc import MetasploitRpcClient, MetasploitRpcError


ClientFactory = Callable[[], MetasploitRpcClient]
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


class ConsoleEventError(Exception):
    def __init__(self, message: str, code: str = "invalid_input") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _safe_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _safe_data(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_data(item) for item in value]
    return value


def _safe_rpc_message(error: MetasploitRpcError) -> str:
    message = str(error) or "Metasploit RPC is unavailable"
    for key, value in os.environ.items():
        if value and any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
            message = message.replace(value, "[REDACTED]")
    return message


def _payload(data: Any) -> Mapping[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ConsoleEventError("Event payload must be an object")
    return data


def _console_id(data: Any) -> str:
    value = _payload(data).get("console_id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ConsoleEventError("A console_id is required")
    normalized = str(value).strip()
    if not normalized:
        raise ConsoleEventError("A console_id is required")
    return normalized


def register_metasploit_socketio(
    socketio: SocketIO,
    client_factory: ClientFactory = MetasploitRpcClient,
) -> None:
    """Register Metasploit console handlers once on a Socket.IO server."""
    if getattr(socketio, "_metasploit_handlers_registered", False):
        return
    socketio._metasploit_handlers_registered = True

    owned_consoles: dict[str, set[str]] = {}
    ownership_lock = threading.Lock()

    def emit_error(event: str, error: Exception, sid: str) -> None:
        if isinstance(error, ConsoleEventError):
            message = error.message
            code = error.code
        elif isinstance(error, MetasploitRpcError):
            message = _safe_rpc_message(error)
            code = "metasploit_unavailable"
        else:
            message = "Unable to process Metasploit console event"
            code = "internal_error"
        socketio.emit(
            "msf_console_error",
            {"event": event, "error": message, "code": code},
            to=sid,
        )

    def require_owner(sid: str, console_id: str) -> None:
        with ownership_lock:
            if console_id not in owned_consoles.get(sid, set()):
                raise ConsoleEventError(
                    "Console is not owned by this connection",
                    "console_not_found",
                )

    @socketio.on("msf_console_create")
    def create_console(data: Any = None) -> None:
        sid = request.sid
        try:
            _payload(data)
            result = client_factory().create_console()
            if not isinstance(result, Mapping) or result.get("id") is None:
                raise MetasploitRpcError(
                    "Metasploit RPC returned an invalid console"
                )
            console_id = str(result["id"])
            with ownership_lock:
                owned_consoles.setdefault(sid, set()).add(console_id)
            socketio.emit(
                "msf_console_created",
                {"console": _safe_data(result)},
                to=sid,
            )
        except Exception as error:
            emit_error("msf_console_create", error, sid)

    @socketio.on("msf_console_write")
    def write_console(data: Any = None) -> None:
        sid = request.sid
        try:
            body = _payload(data)
            console_id = _console_id(body)
            command = body.get("command")
            if not isinstance(command, str):
                raise ConsoleEventError("A command string is required")
            require_owner(sid, console_id)
            if not command.endswith("\n"):
                command += "\n"
            result = client_factory().write_console(console_id, command)
            socketio.emit(
                "msf_console_written",
                {"console_id": console_id, "result": _safe_data(result)},
                to=sid,
            )
        except Exception as error:
            emit_error("msf_console_write", error, sid)

    @socketio.on("msf_console_read")
    def read_console(data: Any = None) -> None:
        sid = request.sid
        try:
            console_id = _console_id(data)
            require_owner(sid, console_id)
            result = client_factory().read_console(console_id)
            socketio.emit(
                "msf_console_output",
                {"console_id": console_id, "output": _safe_data(result)},
                to=sid,
            )
        except Exception as error:
            emit_error("msf_console_read", error, sid)

    @socketio.on("msf_console_destroy")
    def destroy_console(data: Any = None) -> None:
        sid = request.sid
        try:
            console_id = _console_id(data)
            require_owner(sid, console_id)
            result = client_factory().destroy_console(console_id)
            with ownership_lock:
                consoles = owned_consoles.get(sid)
                if consoles is not None:
                    consoles.discard(console_id)
                    if not consoles:
                        owned_consoles.pop(sid, None)
            socketio.emit(
                "msf_console_destroyed",
                {"console_id": console_id, "result": _safe_data(result)},
                to=sid,
            )
        except Exception as error:
            emit_error("msf_console_destroy", error, sid)

    @socketio.on("disconnect")
    def disconnect_console_cleanup() -> None:
        sid = request.sid
        with ownership_lock:
            console_ids = sorted(owned_consoles.pop(sid, set()))
        for console_id in console_ids:
            try:
                client_factory().destroy_console(console_id)
            except Exception:
                # A disconnected browser cannot receive an error. Cleanup is
                # best-effort and intentionally avoids logging RPC details.
                continue
