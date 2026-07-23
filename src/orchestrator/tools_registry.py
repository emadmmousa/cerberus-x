"""Operator-approved custom tool registry.

Lets the AI agent (and operators) extend Firebreak's tool arsenal at runtime with
new wrappers/methods the platform didn't ship. A custom tool is a name + a real
executable + an argument template — the planner may then schedule it exactly like
a built-in wrapper.

Safety model (approval-gated):
- Tools are executed via argv only (never ``shell=True``), so argument content is
  passed literally and cannot inject shell operators.
- Registration is an explicit, audited operator action; the model can *propose* a
  tool in chat, but nothing runs until a human approves it here.
- Bare shell interpreters are rejected as the executable by default so an approved
  tool can't trivially become ``sh -c <model-controlled string>``.

Redis-backed with an in-process fallback (mirrors admin_store / job_store).
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

REGISTRY_KEY = "firebreak:tools:custom"

VALID_RISKS = ("low", "medium", "high")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")
# Executable: no whitespace or shell metacharacters; path-like basenames allowed.
_BINARY_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._/+-]{0,120}$")
_SHELL_BINARIES = frozenset(
    {"sh", "bash", "zsh", "fish", "dash", "ksh", "csh", "tcsh",
     "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh"}
)

_MAX_ARGS = 40

# In-process fallback (authoritative when Redis is unavailable, e.g. tests).
_tools: dict[str, dict[str, Any]] = {}


def custom_tools_file_path() -> Path:
    """Writable JSON store for operator-approved custom tools (survives restarts)."""
    override = os.getenv("FIREBREAK_CUSTOM_TOOLS_FILE")
    if override:
        return Path(override)
    output_dir = os.getenv("FIREBREAK_OUTPUT_DIR")
    if output_dir:
        return Path(output_dir) / "custom_tools.json"
    return Path(__file__).resolve().parents[2] / "output" / "custom_tools.json"


def _ensure_tools_file(path: Path) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"tools": []}, indent=2) + "\n", encoding="utf-8")


def _load_from_file() -> dict[str, dict[str, Any]]:
    path = custom_tools_file_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("tools_registry file load skipped: %s", exc)
        return {}
    items: list[Any]
    if isinstance(raw, dict):
        items = raw.get("tools") or []
    elif isinstance(raw, list):
        items = raw
    else:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        if not name:
            continue
        out[name] = item
    return out


def _save_to_file() -> None:
    path = custom_tools_file_path()
    _ensure_tools_file(path)
    payload = {
        "tools": sorted(
            [_public(rec) for rec in _tools.values()],
            key=lambda row: row.get("name") or "",
        )
    }
    try:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise PermissionError(
            f"cannot write custom tools to {path}: {exc}. "
            "Set FIREBREAK_CUSTOM_TOOLS_FILE to a writable path "
            "(e.g. /app/output/custom_tools.json in Docker)."
        ) from exc


def _redis():
    try:
        from utils.redis_utils import get_redis

        return get_redis()
    except Exception:
        return None


def _load() -> dict[str, dict[str, Any]]:
    """Load custom tools from Redis, falling back to the on-disk registry."""
    loaded = False
    r = _redis()
    if r is not None:
        try:
            raw = r.get(REGISTRY_KEY)
            if raw:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                data = json.loads(raw)
                if isinstance(data, dict):
                    _tools.clear()
                    _tools.update(data)
                    loaded = True
        except Exception as exc:
            logger.debug("tools_registry redis load skipped: %s", exc)

    if not loaded:
        file_data = _load_from_file()
        if file_data:
            _tools.clear()
            _tools.update(file_data)
            loaded = True

    return _tools


def _save() -> None:
    _save_to_file()
    r = _redis()
    if r is None:
        return
    try:
        r.set(REGISTRY_KEY, json.dumps(_tools, default=str))
    except Exception as exc:
        logger.debug("tools_registry redis save skipped: %s", exc)


def _allow_shell_binaries() -> bool:
    return (os.environ.get("FIREBREAK_CUSTOM_TOOL_ALLOW_SHELL") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _builtin_names() -> set[str]:
    try:
        from orchestrator.tasks import _TASK_MAP

        return set(_TASK_MAP.keys())
    except Exception:
        return set()


def _public(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": rec.get("name"),
        "binary": rec.get("binary"),
        "args_template": rec.get("args_template") or [],
        "description": rec.get("description") or "",
        "risk": rec.get("risk") or "medium",
        "category": rec.get("category") or "custom",
        "enabled": bool(rec.get("enabled", True)),
        "created_by": rec.get("created_by"),
        "org_id": rec.get("org_id"),
        "created_at": rec.get("created_at"),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize + validate a custom tool definition. Raises ValueError."""
    name = str(payload.get("name") or "").strip().lower()
    if not _NAME_RE.match(name):
        raise ValueError(
            "name must be lowercase letters/digits/_/- (2-31 chars), start with a letter"
        )
    if name in _builtin_names():
        raise ValueError(f"'{name}' collides with a built-in tool")

    binary = str(payload.get("binary") or "").strip()
    if not _BINARY_RE.match(binary):
        raise ValueError("binary must be a plain executable path (no spaces or shell chars)")
    base = os.path.basename(binary).lower()
    if base in _SHELL_BINARIES and not _allow_shell_binaries():
        raise ValueError(
            f"'{base}' is a shell interpreter and is blocked "
            "(set FIREBREAK_CUSTOM_TOOL_ALLOW_SHELL=true to override)"
        )

    raw_args = payload.get("args_template")
    if raw_args is None:
        raw_args = payload.get("args") or []
    if isinstance(raw_args, str):
        from tools.wrappers._argv import coerce_argv

        raw_args = coerce_argv(raw_args)
    if not isinstance(raw_args, list):
        raise ValueError("args_template must be a list of tokens")
    args_template = [str(a) for a in raw_args][:_MAX_ARGS]

    risk = str(payload.get("risk") or "medium").strip().lower()
    if risk not in VALID_RISKS:
        risk = "medium"

    return {
        "name": name,
        "binary": binary,
        "args_template": args_template,
        "description": str(payload.get("description") or "").strip()[:500],
        "risk": risk,
        "category": str(payload.get("category") or "custom").strip()[:40] or "custom",
    }


def register_tool(
    payload: dict[str, Any],
    *,
    created_by: str | None = None,
    org_id: str | None = None,
) -> dict[str, Any]:
    """Approve + persist a custom tool (overwrites an existing same-name tool)."""
    clean = validate(payload)
    _load()
    import time

    _tools[clean["name"]] = {
        **clean,
        "enabled": True,
        "created_by": created_by,
        "org_id": org_id,
        "created_at": _tools.get(clean["name"], {}).get("created_at") or round(time.time(), 3),
        "updated_at": round(time.time(), 3),
    }
    _save()
    return _public(_tools[clean["name"]])


def delete_tool(name: str) -> bool:
    _load()
    name = (name or "").strip().lower()
    if name not in _tools:
        return False
    _tools.pop(name, None)
    _save()
    return True


def list_tools(*, include_disabled: bool = True) -> list[dict[str, Any]]:
    _load()
    out = [
        _public(rec)
        for rec in _tools.values()
        if include_disabled or rec.get("enabled", True)
    ]
    return sorted(out, key=lambda t: t.get("name") or "")


def get_tool(name: str) -> Optional[dict[str, Any]]:
    _load()
    return _tools.get((name or "").strip().lower())


def custom_tool_names() -> set[str]:
    """Names of enabled custom tools (usable by the planner)."""
    _load()
    return {n for n, r in _tools.items() if r.get("enabled", True)}


def _domain(target: str) -> str:
    value = (target or "").strip()
    if "://" in value:
        value = urlparse(value).hostname or value
    return value.split("/")[0].split(":")[0]


def render_argv(rec: dict[str, Any], target: str, extra_args: list[str] | None) -> list[str]:
    """Build the argv for a custom tool. Placeholders: {target} {domain} {args}."""
    extra_args = [str(a) for a in (extra_args or [])]
    argv = [rec["binary"]]
    used_args = False
    for tok in rec.get("args_template") or []:
        if tok == "{args}":
            argv.extend(extra_args)
            used_args = True
            continue
        argv.append(
            str(tok)
            .replace("{target}", target)
            .replace("{domain}", _domain(target))
            .replace("{url}", target if "://" in target else f"https://{_domain(target)}")
            .replace("{host}", _domain(target))
        )
    if not used_args and extra_args:
        argv.extend(extra_args)
    return argv


def resolve_binary(binary: str) -> Optional[str]:
    """Return an absolute path to the executable if present, else None."""
    if os.path.isabs(binary):
        return binary if os.path.exists(binary) else None
    return shutil.which(binary)


# Common CLI names the agent may invent when not yet wrapped as a built-in.
_TOOL_INVENTIONS: dict[str, dict[str, Any]] = {
    "feroxbuster": {
        "binary": "feroxbuster",
        "args_template": ["-u", "{url}", "-w", "/usr/share/dirb/wordlists/common.txt"],
        "description": "Fast content discovery",
        "risk": "medium",
    },
    "subfinder": {
        "binary": "subfinder",
        "args_template": ["-d", "{domain}", "-silent"],
        "description": "Passive subdomain enumeration",
        "risk": "low",
    },
    "httpx": {
        "binary": "httpx",
        "args_template": ["-silent", "-status-code", "-title", "-tech-detect"],
        "description": "HTTP probe across target variants (ProjectDiscovery httpx)",
        "risk": "low",
    },
    "katana": {
        "binary": "katana",
        "args_template": ["-u", "{url}", "-silent"],
        "description": "Web crawler for endpoint discovery",
        "risk": "medium",
    },
    "curlprobe": {
        "binary": "curl",
        "args_template": ["-sI", "{url}"],
        "description": "Header probe",
        "risk": "low",
    },
    "waybackurls": {
        "binary": "waybackurls",
        "args_template": ["{domain}"],
        "description": "Historical URL discovery",
        "risk": "low",
    },
    "gau": {
        "binary": "gau",
        "args_template": ["{domain}"],
        "description": "Fetch known URLs from archives",
        "risk": "low",
    },
}


def invent_tool(
    name: str,
    *,
    phase_args: list[str] | None = None,
) -> Optional[dict[str, Any]]:
    """Build a registerable custom tool definition for a missing tool name."""
    key = (name or "").strip().lower()
    if not key or key in _builtin_names():
        return None
    base = _TOOL_INVENTIONS.get(key)
    if not base:
        # Same-name binary on PATH is a reasonable default wrapper.
        if resolve_binary(key):
            base = {
                "binary": key,
                "args_template": ["{target}", "{args}"],
                "description": f"Auto wrapper for {key}",
                "risk": "medium",
            }
        elif phase_args:
            candidate = str(phase_args[0]).strip()
            if resolve_binary(candidate):
                base = {
                    "binary": candidate,
                    "args_template": ["{args}"],
                    "description": f"Auto wrapper for {key} via {candidate}",
                    "risk": "medium",
                }
        if not base:
            return None
    try:
        return validate({"name": key, **base})
    except ValueError:
        return None


def _coerce_tool_definition(raw: Any) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    try:
        return validate(raw)
    except ValueError:
        name = str(raw.get("name") or "").strip().lower()
        if name:
            return invent_tool(name)
        return None


def collect_tool_definitions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Gather registerable custom tool defs from plan new_tools + phase references."""
    builtins = _builtin_names()
    by_name: dict[str, dict[str, Any]] = {}

    for raw in plan.get("new_tools") or []:
        clean = _coerce_tool_definition(raw)
        if clean and clean["name"] not in builtins:
            by_name[clean["name"]] = clean

    for phase in plan.get("phases") or []:
        if not isinstance(phase, dict):
            continue
        for tool_entry in phase.get("tools") or []:
            if not isinstance(tool_entry, dict):
                continue
            name = str(tool_entry.get("tool") or "").strip().lower()
            if not name or name in builtins or name in by_name:
                continue
            if get_tool(name):
                continue
            phase_args = tool_entry.get("args") or []
            if not isinstance(phase_args, list):
                phase_args = []
            invented = invent_tool(name, phase_args=[str(a) for a in phase_args])
            if invented:
                by_name[invented["name"]] = invented

    return sorted(by_name.values(), key=lambda row: row.get("name") or "")


def ensure_plan_new_tools(plan: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the plan with new_tools populated for every custom phase tool."""
    if not isinstance(plan, dict):
        return plan
    out = dict(plan)
    out["new_tools"] = collect_tool_definitions(out)
    return out


def register_plan_tools(
    plan: dict[str, Any],
    *,
    created_by: str | None = None,
    org_id: str | None = None,
) -> list[str]:
    """Persist every custom tool referenced by a mission plan before execution."""
    enriched = ensure_plan_new_tools(plan or {})
    registered: list[str] = []
    for raw in enriched.get("new_tools") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip().lower()
        if not name:
            continue
        if get_tool(name):
            continue
        row = register_tool(raw, created_by=created_by, org_id=org_id)
        registered.append(row["name"])
    return registered


def register_tools(
    entries: list[dict[str, Any]],
    *,
    created_by: str | None = None,
    org_id: str | None = None,
) -> list[dict[str, Any]]:
    """Register many custom tools; skip invalid entries."""
    registered: list[dict[str, Any]] = []
    for raw in entries or []:
        if not isinstance(raw, dict):
            continue
        try:
            registered.append(register_tool(raw, created_by=created_by, org_id=org_id))
        except ValueError:
            continue
    return registered


def preload_custom_tools() -> int:
    """Load persisted custom tools at process startup."""
    _load()
    return len(_tools)
