"""Playbook wrapper for executing explicit Metasploit modules over RPC."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..metasploit_rpc import MetasploitRpcClient, MetasploitRpcError


DEFAULT_MODULE = "auxiliary/scanner/portscan/tcp"


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


def _parse_args(
    args: list[str] | None,
) -> tuple[str, str, str, dict[str, Any]]:
    if args is None:
        args = [DEFAULT_MODULE]
    if not args:
        raise ValueError("Metasploit module path is required")

    module = args[0]
    if not isinstance(module, str):
        raise ValueError("Metasploit module path must be a string")
    module = module.strip()
    if "/" not in module:
        raise ValueError("Metasploit module must use a full module path")
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



def scan(target: str, args: list[str] | None = None) -> dict[str, Any]:
    """Validate and execute one explicit Metasploit module over RPC."""
    try:
        module, module_type, module_name, options = _parse_args(args)
    except ValueError as exc:
        return _error(target, "invalid_arguments", str(exc))

    options.setdefault("RHOSTS", _host(target))

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

        response = client.execute_module(module_type, module_name, options)
        if not isinstance(response, dict):
            return _error(
                target,
                "rpc_error",
                "Metasploit RPC returned an invalid execution response",
                module=module,
            )
        return {
            "tool": "metasploit",
            "target": target,
            "module": module,
            "job_id": response.get("job_id"),
            "uuid": response.get("uuid"),
            "response": response,
            "raw_output": (
                f"module={module} job_id={response.get('job_id')} "
                f"uuid={response.get('uuid')}"
            ),
        }
    except MetasploitRpcError as exc:
        return _error(target, "rpc_error", str(exc), module=module)
    except Exception:
        return _error(
            target,
            "rpc_error",
            "Metasploit RPC execution failed",
            module=module,
        )
