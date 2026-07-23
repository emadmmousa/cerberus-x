"""Every scaffold must be runnable end-to-end through tools/wrappers.

These tests guard the full dispatch chain:
    scaffold/<id> -> run_scaffold_bundle_task -> scaffold_bundle.scan()
    -> tools_for_scaffold() bundle -> _runner(child) via _SCANNERS

A new scaffold or a new bundle tool that lacks a registered/importable wrapper
must fail here rather than silently erroring at mission runtime.
"""

from __future__ import annotations

from orchestrator.ai.scaffold_tools import (
    EXPECTED_SCAFFOLD_COUNT,
    get_scaffold_registry,
    resolve_scaffold_id,
)
from orchestrator.tasks import _TASK_MAP, run_scaffold_bundle_task
from tools.wrappers import scaffold_bundle


def test_every_bundle_tool_has_registered_wrapper():
    # Membership guard: no scaffold references a tool without a wrapper runner.
    assert scaffold_bundle.missing_bundle_runners() == []


def test_all_registered_wrappers_import_and_are_callable():
    # Deep guard: every _SCANNERS entry imports and exposes a callable.
    assert scaffold_bundle.unimportable_scanner_tools() == []


def test_assert_bundles_runnable_returns_tool_count():
    count = scaffold_bundle.assert_bundles_runnable()
    # 160 scaffolds resolve down to a bounded set of atomic CLI wrappers.
    assert count > 0
    assert count <= len(scaffold_bundle.registered_scanner_tools())


def test_all_160_scaffolds_resolve_to_runnable_bundles():
    registry = get_scaffold_registry()
    assert len(registry) == EXPECTED_SCAFFOLD_COUNT
    runnable = scaffold_bundle.registered_scanner_tools()
    for sid, bundle in registry.items():
        assert bundle, f"scaffold {sid} has an empty bundle"
        for tool in bundle:
            assert tool in runnable, f"scaffold {sid} -> {tool} has no wrapper"


def test_every_scaffold_dispatches_through_wrappers(monkeypatch):
    """Drive scaffold_bundle.scan() for all 160 scaffolds with fake runners.

    Proves the dispatch loop invokes a wrapper for every child tool and
    aggregates results — no scaffold falls through to "no wrapper registered".
    """
    invoked: list[tuple[str, str]] = []

    def make_fake(tool_name: str):
        def _fake(target, args=None, evasion=None):
            invoked.append((tool_name, target))
            return {"tool": tool_name, "target": target, "productive": True}

        return _fake

    # Route every registered tool to a recording fake runner.
    monkeypatch.setattr(
        scaffold_bundle,
        "_runner",
        lambda name: make_fake(name) if name in scaffold_bundle._SCANNERS else None,
    )

    registry = get_scaffold_registry()
    for sid, bundle in registry.items():
        invoked.clear()
        result = scaffold_bundle.scan("https://authorized.example", scaffold_id=sid)
        assert result["tool"] == f"scaffold/{sid}"
        assert result["scaffold_id"] == sid
        assert result["errors"] == [], f"{sid} produced errors: {result['errors']}"
        assert result["productive"] is True
        assert [t for t, _ in invoked] == bundle, f"{sid} dispatch mismatch"


def test_task_map_routes_every_scaffold_to_bundle_task():
    scaffolds = [name for name in _TASK_MAP if name.startswith("scaffold/")]
    assert len(scaffolds) == EXPECTED_SCAFFOLD_COUNT
    for name in scaffolds:
        assert _TASK_MAP[name] is run_scaffold_bundle_task
        # And the scaffold id round-trips to a wired bundle.
        sid = resolve_scaffold_id(name)
        assert get_scaffold_registry()[sid]
