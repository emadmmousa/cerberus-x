"""Execute a specialist scaffold bundle — runs mapped CLI wrappers in sequence."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from tools.normalize_args import normalize_tool_args

# tool name → (module path, callable name)
_SCANNERS: dict[str, tuple[str, str]] = {
    "nmap": ("tools.wrappers.nmap", "scan"),
    "gobuster": ("tools.wrappers.gobuster", "scan"),
    "whatweb": ("tools.wrappers.whatweb", "scan"),
    "sqlmap": ("tools.wrappers.sqlmap", "scan"),
    "nuclei": ("tools.wrappers.nuclei", "scan"),
    "metasploit": ("tools.wrappers.metasploit", "scan"),
    "masscan": ("tools.wrappers.masscan", "scan"),
    "rustscan": ("tools.wrappers.rustscan", "scan"),
    "theharvester": ("tools.wrappers.theharvester", "scan"),
    "ffuf": ("tools.wrappers.ffuf", "scan"),
    "hydra": ("tools.wrappers.hydra", "scan"),
    "john": ("tools.wrappers.john", "scan"),
    "hashcat": ("tools.wrappers.hashcat", "scan"),
    "winpeas": ("tools.wrappers.winpeas", "scan"),
    "linpeas": ("tools.wrappers.linpeas", "scan"),
    "zmap": ("tools.wrappers.zmap", "scan"),
    "nikto": ("tools.wrappers.nikto", "scan"),
    "xsstrike": ("tools.wrappers.xsstrike", "scan"),
    "impacket": ("tools.wrappers.impacket", "scan"),
    "crackmapexec": ("tools.wrappers.crackmapexec", "scan"),
    "responder": ("tools.wrappers.responder", "scan"),
    "bloodhound": ("tools.wrappers.bloodhound", "scan"),
    "sliver": ("tools.wrappers.sliver", "scan"),
    "darkweb": ("tools.wrappers.darkweb", "scan"),
    "httpx": ("tools.wrappers.httpx_probe", "scan"),
    "breach_intel": ("tools.wrappers.breach_intel", "run"),
    "katana": ("tools.wrappers.katana", "scan"),
    "subfinder": ("tools.wrappers.subfinder", "scan"),
    "gau": ("tools.wrappers.gau", "scan"),
    "sherlock": ("tools.wrappers.sherlock", "scan"),
    "feroxbuster": ("tools.wrappers.feroxbuster", "scan"),
    "naabu": ("tools.wrappers.naabu", "scan"),
    "dnsx": ("tools.wrappers.dnsx", "scan"),
    "amass": ("tools.wrappers.amass", "scan"),
    "dalfox": ("tools.wrappers.dalfox", "scan"),
    "waybackurls": ("tools.wrappers.waybackurls", "scan"),
    "sslscan": ("tools.wrappers.sslscan", "scan"),
    "arjun": ("tools.wrappers.arjun", "scan"),
    "enum4linux": ("tools.wrappers.enum4linux", "scan"),
    "commix": ("tools.wrappers.commix", "scan"),
    "wpscan": ("tools.wrappers.wpscan", "scan"),
}

_fn_cache: dict[str, Callable[..., Any]] = {}


def _runner(tool_name: str) -> Callable[..., Any] | None:
    if tool_name in _fn_cache:
        return _fn_cache[tool_name]
    spec = _SCANNERS.get(tool_name)
    if not spec:
        return None
    module = importlib.import_module(spec[0])
    fn = getattr(module, spec[1])
    _fn_cache[tool_name] = fn
    return fn


def registered_scanner_tools() -> set[str]:
    """CLI tools that have a wrapper runner registered for scaffold execution."""
    return set(_SCANNERS)


def missing_bundle_runners() -> list[str]:
    """Tools referenced by any scaffold bundle that lack a registered wrapper.

    Membership-only (no wrapper imports), so it is cheap enough to run at import
    time. An empty list means every scaffold is dispatchable end-to-end.
    """
    from orchestrator.ai.scaffold_tools import get_scaffold_registry

    referenced: set[str] = set()
    for tools in get_scaffold_registry().values():
        referenced.update(tools)
    return sorted(tool for tool in referenced if tool not in _SCANNERS)


def unimportable_scanner_tools() -> list[tuple[str, str]]:
    """Registered wrappers whose module/callable fails to import or is not callable.

    Performs real imports, so call it from tests/CI rather than at import time.
    Returns ``(tool_name, reason)`` pairs; an empty list means all runnable.
    """
    broken: list[tuple[str, str]] = []
    for tool, (module_path, fn_name) in _SCANNERS.items():
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:  # noqa: BLE001
            broken.append((tool, f"import {module_path} failed: {exc!r}"))
            continue
        fn = getattr(module, fn_name, None)
        if not callable(fn):
            broken.append((tool, f"{module_path}.{fn_name} is not callable"))
    return broken


def assert_bundles_runnable() -> int:
    """Fail fast when a scaffold bundle references a tool with no wrapper runner.

    Returns the number of distinct runnable tools referenced across all bundles.
    """
    missing = missing_bundle_runners()
    if missing:
        raise AssertionError(
            "scaffold bundles reference tools without a registered wrapper "
            f"(add them to scaffold_bundle._SCANNERS): {missing}"
        )
    from orchestrator.ai.scaffold_tools import get_scaffold_registry

    referenced: set[str] = set()
    for tools in get_scaffold_registry().values():
        referenced.update(tools)
    return len(referenced)


def scan(
    target,
    args=None,
    evasion=None,
    *,
    scaffold_id: str | None = None,
    tool_name: str | None = None,
):
    """Run every CLI wrapper mapped to this scaffold specialist recipe."""
    sid = (scaffold_id or "").strip().lower()
    if not sid and tool_name:
        from orchestrator.ai.scaffold_tools import resolve_scaffold_id

        sid = resolve_scaffold_id(tool_name) or ""
    if not sid:
        return {
            "tool": tool_name or "scaffold/unknown",
            "target": target,
            "error": "scaffold_id required",
            "productive": False,
        }

    virtual_name = f"scaffold/{sid}"
    from orchestrator.ai.scaffold_tools import tools_for_scaffold

    bundle = tools_for_scaffold(sid)
    extra_args = list(args or [])
    evasion = evasion or {}

    child_results: list[dict[str, Any]] = []
    errors: list[str] = []
    productive = False

    for child in bundle:
        runner = _runner(child)
        if runner is None:
            errors.append(f"{child}: no wrapper registered")
            continue
        child_args = normalize_tool_args(child, target, extra_args, evasion=evasion)
        try:
            result = runner(target, child_args, evasion)
        except TypeError:
            try:
                result = runner(target, child_args)
            except TypeError:
                result = runner(target)
        except Exception as exc:  # noqa: BLE001
            result = {"tool": child, "target": target, "error": str(exc)}

        if isinstance(result, dict):
            result.setdefault("tool", child)
            child_results.append(result)
            if result.get("productive") or result.get("ports") or result.get("findings"):
                productive = True
            if result.get("error"):
                errors.append(f"{child}: {result['error'][:120]}")

    return {
        "tool": virtual_name,
        "scaffold_id": sid,
        "target": target,
        "bundle_tools": bundle,
        "bundle_count": len(bundle),
        "child_results": child_results,
        "errors": errors[:12],
        "productive": productive or bool(child_results),
    }


# Fail fast at import if any scaffold bundle references a tool with no wrapper
# runner — keeps every one of the 160 scaffolds dispatchable end-to-end.
assert_bundles_runnable()
