"""MessagePack client for the Metasploit Framework RPC API."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import msgpack
import requests


class MetasploitRpcError(Exception):
    """Base exception for safe-to-display RPC client failures."""

    def __init__(self, message: str, *, method: str | None = None) -> None:
        super().__init__(message)
        self.method = method


class MetasploitRpcConfigError(MetasploitRpcError):
    """Raised when RPC environment configuration is invalid."""


class MetasploitRpcAuthError(MetasploitRpcError):
    """Raised when Metasploit rejects RPC authentication."""


class MetasploitRpcConnectionError(MetasploitRpcError):
    """Raised when the RPC endpoint cannot be reached."""


class MetasploitRpcTimeoutError(MetasploitRpcConnectionError):
    """Raised when an RPC request exceeds its configured timeout."""


@dataclass(frozen=True)
class MetasploitRpcConfig:
    host: str = "metasploit"
    port: int = 55553
    username: str = "msf"
    password: str = field(default="", repr=False)
    ssl: bool = False
    verify_ssl: bool = False
    timeout: float = 10.0
    retries: int = 2
    retry_delay: float = 0.2

    def __post_init__(self) -> None:
        if not self.host:
            raise MetasploitRpcConfigError("MSF_RPC_HOST must not be empty")
        if not self.username:
            raise MetasploitRpcConfigError("MSF_RPC_USER must not be empty")
        if not self.password:
            raise MetasploitRpcConfigError("MSF_RPC_PASSWORD is required")
        if not 1 <= self.port <= 65535:
            raise MetasploitRpcConfigError("MSF_RPC_PORT must be between 1 and 65535")
        if self.timeout <= 0:
            raise MetasploitRpcConfigError("MSF_RPC_TIMEOUT must be greater than zero")
        if self.retries < 0:
            raise MetasploitRpcConfigError("MSF_RPC_RETRIES must not be negative")
        if self.retry_delay < 0:
            raise MetasploitRpcConfigError(
                "MSF_RPC_RETRY_DELAY must not be negative"
            )

    @classmethod
    def from_env(cls) -> "MetasploitRpcConfig":
        password = os.getenv("MSF_RPC_PASSWORD")
        if not password:
            raise MetasploitRpcConfigError("MSF_RPC_PASSWORD is required")

        try:
            return cls(
                host=os.getenv("MSF_RPC_HOST", "metasploit"),
                port=int(os.getenv("MSF_RPC_PORT", "55553")),
                username=os.getenv("MSF_RPC_USER", "msf"),
                password=password,
                ssl=_parse_bool(os.getenv("MSF_RPC_SSL", "false")),
                verify_ssl=_parse_bool(
                    os.getenv("MSF_RPC_VERIFY_SSL", "false")
                ),
                timeout=float(os.getenv("MSF_RPC_TIMEOUT", "10")),
                retries=int(os.getenv("MSF_RPC_RETRIES", "2")),
                retry_delay=float(os.getenv("MSF_RPC_RETRY_DELAY", "0.2")),
            )
        except ValueError as exc:
            raise MetasploitRpcConfigError(
                "Metasploit RPC environment contains an invalid value"
            ) from exc


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("invalid boolean")


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(_json_safe(key)): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class MetasploitRpcClient:
    """Authenticated client for Metasploit's MessagePack RPC endpoint."""

    def __init__(
        self,
        config: MetasploitRpcConfig | None = None,
        *,
        session: requests.Session | None = None,
    ) -> None:
        self.config = config or MetasploitRpcConfig.from_env()
        self.session = session or requests.Session()
        scheme = "https" if self.config.ssl else "http"
        self.endpoint = f"{scheme}://{self.config.host}:{self.config.port}/api/"
        self._token: str | None = None
        self._auth_lock = threading.Lock()

    def authenticate(self) -> None:
        if self._token is not None:
            return

        with self._auth_lock:
            if self._token is not None:
                return
            response = self._request(
                "auth.login",
                self.config.username,
                self.config.password,
                authenticated=False,
            )
            token = response.get("token") if isinstance(response, dict) else None
            if (
                not isinstance(response, dict)
                or response.get("result") != "success"
                or not token
            ):
                raise MetasploitRpcAuthError(
                    self._error_message(
                        response, "Metasploit RPC authentication failed"
                    ),
                    method="auth.login",
                )
            self._token = str(token)

    def call(self, method: str, *args: Any) -> Any:
        if not method or method == "auth.login":
            raise MetasploitRpcError("Invalid RPC method")
        self.authenticate()
        try:
            return self._request(method, *args, authenticated=True)
        except MetasploitRpcAuthError:
            self._token = None
            self.authenticate()
            return self._request(method, *args, authenticated=True)

    def _request(self, method: str, *args: Any, authenticated: bool) -> Any:
        payload = [method]
        if authenticated:
            if self._token is None:
                raise MetasploitRpcAuthError("Metasploit RPC authentication failed")
            payload.append(self._token)
        payload.extend(args)
        packed_payload = msgpack.packb(payload, use_bin_type=True)

        response = None
        for attempt in range(self.config.retries + 1):
            try:
                response = self.session.post(
                    self.endpoint,
                    data=packed_payload,
                    headers={"Content-Type": "binary/message-pack"},
                    timeout=self.config.timeout,
                    verify=self.config.verify_ssl,
                )
                response.raise_for_status()
                break
            except requests.Timeout:
                if attempt == self.config.retries:
                    raise MetasploitRpcTimeoutError(
                        "Metasploit RPC request timed out", method=method
                    ) from None
            except requests.RequestException:
                if attempt == self.config.retries:
                    raise MetasploitRpcConnectionError(
                        "Metasploit RPC request failed", method=method
                    ) from None

            if self.config.retry_delay:
                time.sleep(self.config.retry_delay)

        try:
            unpacked = msgpack.unpackb(response.content, raw=False, strict_map_key=False)
        except (msgpack.ExtraData, msgpack.FormatError, msgpack.StackError, ValueError) as exc:
            raise MetasploitRpcError(
                "Metasploit RPC returned an invalid response", method=method
            ) from exc

        normalized = _json_safe(unpacked)
        if isinstance(normalized, dict) and (
            normalized.get("error") or normalized.get("result") == "failure"
        ):
            if method == "auth.login":
                return normalized
            message = self._error_message(
                normalized, "Metasploit RPC call failed"
            )
            if self._is_token_error(normalized):
                raise MetasploitRpcAuthError(message, method=method)
            raise MetasploitRpcError(message, method=method)
        return normalized

    def _error_message(self, response: Any, fallback: str) -> str:
        if not isinstance(response, dict):
            return fallback
        message = response.get("error_message")
        if not isinstance(message, str) or not message.strip():
            return fallback
        sanitized = message
        for secret in (self.config.password, self._token):
            if secret:
                sanitized = sanitized.replace(secret, "[REDACTED]")
        return sanitized

    @staticmethod
    def _is_token_error(response: dict[str, Any]) -> bool:
        message = str(response.get("error_message", "")).lower()
        return (
            "invalid authentication token" in message
            or "invalid token" in message
            or ("token" in message and "expired" in message)
        )

    def search_modules(
        self, query: str, *, module_type: str | None = None
    ) -> Any:
        search = query.strip()
        if module_type:
            search = f"{search} type:{module_type}".strip()
        return self.call("module.search", search)

    def module_info(self, module_type: str, module_name: str) -> Any:
        return self.call("module.info", module_type, module_name)

    def module_options(self, module_type: str, module_name: str) -> Any:
        return self.call("module.options", module_type, module_name)

    def execute_module(
        self, module_type: str, module_name: str, options: dict[str, Any]
    ) -> Any:
        return self.call("module.execute", module_type, module_name, options)

    def list_jobs(self) -> Any:
        return self.call("job.list")

    def stop_job(self, job_id: str | int) -> Any:
        return self.call("job.stop", str(job_id))

    def list_sessions(self) -> Any:
        return self.call("session.list")

    def write_session(
        self,
        session_id: str | int,
        command: str,
        *,
        session_type: str = "shell",
    ) -> Any:
        method = self._session_method(session_type, "write")
        return self.call(method, str(session_id), command)

    def read_session(
        self, session_id: str | int, *, session_type: str = "shell"
    ) -> Any:
        method = self._session_method(session_type, "read")
        return self.call(method, str(session_id))

    @staticmethod
    def _session_method(session_type: str, operation: str) -> str:
        normalized_type = session_type.strip().lower()
        if normalized_type not in {"shell", "meterpreter"}:
            raise MetasploitRpcError(
                f"Unsupported session type: {session_type}"
            )
        return f"session.{normalized_type}_{operation}"

    def stop_session(self, session_id: str | int) -> Any:
        return self.call("session.stop", str(session_id))

    def create_console(self) -> Any:
        return self.call("console.create")

    def list_consoles(self) -> Any:
        return self.call("console.list")

    def read_console(self, console_id: str | int) -> Any:
        return self.call("console.read", str(console_id))

    def write_console(self, console_id: str | int, command: str) -> Any:
        return self.call("console.write", str(console_id), command)

    def destroy_console(self, console_id: str | int) -> Any:
        return self.call("console.destroy", str(console_id))
