"""Playbook wrapper for executing explicit Metasploit modules over RPC."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

from ..metasploit_rpc import MetasploitRpcClient, MetasploitRpcError


DEFAULT_MODULE = "auxiliary/scanner/portscan/tcp"
DEFAULT_JOB_WAIT_SECONDS = 90
DEFAULT_JOB_POLL_INTERVAL = 2.0

MSF_MODULE_TYPES = frozenset({"exploit", "auxiliary", "post", "payload", "encoder", "nop"})

# Common planner/LLM shorthands → full MSF module paths.
MODULE_ALIASES: dict[str, str] = {
    "portscan": DEFAULT_MODULE,
    "tcp_portscan": DEFAULT_MODULE,
    "http_version": "auxiliary/scanner/http/http_version",
    "ssl_version": "auxiliary/scanner/ssl/ssl_version",
    "dir_scanner": "auxiliary/scanner/http/dir_scanner",
    "wordpress_scanner": "auxiliary/scanner/http/wordpress_scanner",
    "apache_path_traversal": "exploit/multi/http/apache_path_traversal",
    "log4shell": "exploit/multi/http/log4shell_header_injection",
    "log4shell_header_injection": "exploit/multi/http/log4shell_header_injection",
    "ms17_010": "exploit/windows/smb/ms17_010_eternalblue",
    "eternalblue": "exploit/windows/smb/ms17_010_eternalblue",
    "bluekeep": "exploit/windows/rdp/cve_2019_0708_bluekeep_rce",
}


_IPV4_CIDR = re.compile(
    r"^(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}$"
)
_IPV4_HOST_PORT = re.compile(
    r"^((?:\d{1,3}\.){3}\d{1,3}):(\d+)$"
)
_IPV6_BRACKETED = re.compile(
    r"^\[([^\]]+)\](?::(\d+))?$"
)
_IPV6_CIDR = re.compile(
    r"^([0-9a-fA-F:]+)/\d{1,3}$"
)


def _host(target: str) -> str:
    """Derive Metasploit RHOSTS from a URL, host:port, or CIDR target."""
    value = target.strip()
    if "://" in value:
        return urlparse(value).hostname or value

    bracketed = _IPV6_BRACKETED.fullmatch(value)
    if bracketed:
        return bracketed.group(1)

    if _IPV4_CIDR.fullmatch(value) or _IPV6_CIDR.fullmatch(value):
        return value

    ipv4_port = _IPV4_HOST_PORT.fullmatch(value)
    if ipv4_port:
        return ipv4_port.group(1)

    return value


def _classify_rpc_error(message: str) -> str:
    lower = (message or "").lower()
    if "invalid module" in lower:
        return "invalid_module"
    return "rpc_error"


def _error(
    target: str,
    code: str,
    message: str,
    *,
    module: str | None = None,
) -> dict[str, Any]:
    result = {
        "tool": "metasploit",
        "target": target,
        "code": code,
        "error": message,
    }
    if module is not None:
        result["module"] = module
    return result


def _coerce_option(value: str) -> str | bool | int:
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"[+-]?\d+", normalized):
        return int(normalized)
    return normalized


def _module_from_shorthand(name: str) -> str | None:
    """Resolve bare module names via aliases and the CVE/port exploit maps."""
    key = name.strip().lower().strip("/")
    if not key:
        return None
    alias = MODULE_ALIASES.get(key)
    if alias:
        return alias
    try:
        from tools.cve_exploit_map import CVE_EXPLOIT_MAP, SERVICE_PORT_EXPLOITS
    except ImportError:
        return None
    for module, _ in CVE_EXPLOIT_MAP.values():
        if key == module or key == module.rsplit("/", 1)[-1]:
            return module
    for specs in SERVICE_PORT_EXPLOITS.values():
        for module, _ in specs:
            if key == module or key == module.rsplit("/", 1)[-1]:
                return module
    return None


def normalize_module_path(raw: str) -> str:
    """Coerce planner/LLM module tokens into a full Metasploit module path."""
    value = (raw or "").strip()
    if not value:
        raise ValueError("Metasploit module path is required")
    value = value.strip("/")
    first = value.split("/", 1)[0].lower()

    if first in MSF_MODULE_TYPES:
        if "/" not in value or not value.split("/", 1)[1]:
            raise ValueError("Metasploit module must use a full module path")
        return value

    if first in {"scanner", "gather", "admin", "server", "dos", "fuzzers", "client"}:
        return f"auxiliary/{value}"

    if first in {
        "multi",
        "linux",
        "windows",
        "osx",
        "bsd",
        "solaris",
        "aix",
        "unix",
        "android",
        "apple_ios",
    }:
        return f"exploit/{value}"

    resolved = _module_from_shorthand(value)
    if resolved:
        return resolved

    if "/" in value:
        return f"auxiliary/{value}"

    raise ValueError("Metasploit module must use a full module path")


def _parse_args(
    args: list[str] | None,
) -> tuple[str, str, str, dict[str, Any]]:
    if not args:
        args = [DEFAULT_MODULE]
    if not args:
        raise ValueError("Metasploit module path is required")

    if not isinstance(args[0], str):
        raise ValueError("Metasploit module path must be a string")

    module = normalize_module_path(args[0])
    module_type, module_name = module.split("/", 1)
    if not module_type or not module_name:
        raise ValueError("Metasploit module must use a full module path")

    options: dict[str, Any] = {}
    for argument in args[1:]:
        if not isinstance(argument, str) or "=" not in argument:
            raise ValueError("Metasploit options must use KEY=VALUE")
        key, value = argument.split("=", 1)
        key = key.strip().upper()
        if not key:
            raise ValueError("Metasploit option key must not be empty")
        options[key] = _coerce_option(value)

    return module, module_type, module_name, options


def _missing_required_options(
    definitions: dict[str, Any], options: dict[str, Any]
) -> list[str]:
    missing = []
    for name, metadata in definitions.items():
        if not isinstance(metadata, dict) or metadata.get("required") is not True:
            continue
        supplied = name in options and options[name] not in ("", None)
        has_default = metadata.get("default") not in ("", None)
        if not supplied and not has_default:
            missing.append(name)
    return sorted(missing)


def _wait_for_job(
    client: MetasploitRpcClient,
    job_id: str | int | None,
    timeout: float = DEFAULT_JOB_WAIT_SECONDS,
) -> bool:
    if job_id is None:
        return True

    deadline = time.monotonic() + timeout
    job_key = str(job_id)
    while time.monotonic() < deadline:
        jobs = client.list_jobs() or {}
        if isinstance(jobs, dict) and job_key not in {str(key) for key in jobs}:
            return True
        time.sleep(DEFAULT_JOB_POLL_INTERVAL)
    return False


def _post_module_has_explicit_success(response: dict[str, Any]) -> bool:
    """True only when the RPC response carries a confirmed post-module success."""
    return False


def _post_module_status(response: dict[str, Any]) -> str:
    if _post_module_has_explicit_success(response):
        return "completed"
    return "attempted"


def _new_sessions_for_target(
    sessions: Any,
    existing_sessions: Any,
    host: str,
) -> list[dict[str, str]]:
    result = []
    if not isinstance(sessions, dict):
        return result
    existing_ids = (
        {str(session_id) for session_id in existing_sessions}
        if isinstance(existing_sessions, dict)
        else set()
    )

    for session_id, metadata in sessions.items():
        if str(session_id) in existing_ids:
            continue
        if not isinstance(metadata, dict):
            continue
        target_host = str(
            metadata.get("target_host") or metadata.get("tunnel_peer") or ""
        )
        if (
            host
            and target_host
            and host not in target_host
            and target_host not in host
        ):
            continue
        result.append(
            {
                "id": str(session_id),
                "type": str(metadata.get("type") or "shell"),
                "platform": str(
                    metadata.get("platform")
                    or metadata.get("arch")
                    or metadata.get("info")
                    or ""
                ),
                "desc": str(metadata.get("desc") or metadata.get("info") or ""),
            }
        )
    return result



def scan(target: str, args: list[str] | None = None) -> dict[str, Any]:
    """Validate and execute one explicit Metasploit module over RPC."""
    try:
        module, module_type, module_name, options = _parse_args(args)
    except ValueError as exc:
        return _error(target, "invalid_arguments", str(exc))

    options.setdefault("RHOSTS", _host(target))

    # For exploits, fill workable PAYLOAD/LHOST/LPORT when callers omitted them
    # (or passed the historical LHOST=0.0.0.0 stub).
    if module_type == "exploit":
        from tools.payload_strategy import resolve_exploit_options

        stubs = [f"{key}={value}" for key, value in options.items()]
        resolved = resolve_exploit_options(module, target=target, existing=stubs)
        for item in resolved:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            options[key.strip().upper()] = _coerce_option(value)

    try:
        client = MetasploitRpcClient()
        definitions = client.module_options(module_type, module_name)
        if not isinstance(definitions, dict):
            return _error(
                target,
                "rpc_error",
                "Metasploit RPC returned invalid module options",
                module=module,
            )

        missing = _missing_required_options(definitions, options)
        if missing:
            return _error(
                target,
                "missing_required_options",
                f"Missing required module options: {', '.join(missing)}",
                module=module,
            )

        existing_sessions = client.list_sessions()
        response = client.execute_module(module_type, module_name, options)
        if not isinstance(response, dict):
            return _error(
                target,
                "rpc_error",
                "Metasploit RPC returned an invalid execution response",
                module=module,
            )
        if not _wait_for_job(client, response.get("job_id")):
            return _error(
                target,
                "job_timeout",
                "Metasploit job timed out before completion",
                module=module,
            )
        sessions = _new_sessions_for_target(
            client.list_sessions(),
            existing_sessions,
            _host(target),
        )
        status = (
            _post_module_status(response)
            if module_type == "post"
            else "completed"
        )
        result = {
            "tool": "metasploit",
            "target": target,
            "module": module,
            "job_id": response.get("job_id"),
            "uuid": response.get("uuid"),
            "response": response,
            "sessions": sessions,
            "status": status,
            "raw_output": (
                f"module={module} job_id={response.get('job_id')} "
                f"uuid={response.get('uuid')}"
            ),
        }
        if sessions and module_type == "exploit":
            result["vulnerable"] = True
        if module_type == "exploit":
            result["payload"] = {
                "PAYLOAD": options.get("PAYLOAD"),
                "LHOST": options.get("LHOST"),
                "LPORT": options.get("LPORT"),
                "RPORT": options.get("RPORT"),
            }
        return result
    except MetasploitRpcError as exc:
        return _error(
            target,
            _classify_rpc_error(str(exc)),
            str(exc),
            module=module,
        )
    except Exception:
        return _error(
            target,
            "rpc_error",
            "Metasploit RPC execution failed",
            module=module,
        )
