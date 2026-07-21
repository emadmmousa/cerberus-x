"""Best-of-N / merge consensus for multi-scaffold plans (Firebreak W1)."""

from __future__ import annotations

from typing import Any


def _tool_names(plan: dict[str, Any]) -> set[str]:
    names = set()
    for entry in plan.get("tools") or []:
        if isinstance(entry, dict) and entry.get("tool"):
            names.add(str(entry["tool"]))
    return names


def pick_best_plan(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer non-stop plans with the most unique tools; tie-break by first."""
    viable = [c for c in candidates if isinstance(c, dict)]
    if not viable:
        return None
    ranked = sorted(
        viable,
        key=lambda p: (
            0 if p.get("stop") else 1,
            len(_tool_names(p)),
            1 if p.get("tools") else 0,
        ),
        reverse=True,
    )
    best = dict(ranked[0])
    best["consensus"] = {
        "candidates": len(viable),
        "tool_counts": [len(_tool_names(p)) for p in viable],
        "sources": [p.get("scaffold_id") or p.get("source") for p in viable],
    }
    return best


def agreement_score(candidates: list[dict[str, Any]]) -> float:
    """Mean pairwise Jaccard overlap of candidate tool sets (0.0–1.0).

    1.0 = every scaffold proposed the same tools; 0.0 = no overlap.
    A single candidate is treated as full agreement.
    """
    sets = [_tool_names(c) for c in candidates if isinstance(c, dict)]
    if len(sets) < 2:
        return 1.0
    scores: list[float] = []
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = sets[i] | sets[j]
            if not union:
                scores.append(1.0)
                continue
            scores.append(len(sets[i] & sets[j]) / len(union))
    return round(sum(scores) / len(scores), 3) if scores else 1.0


def summarize_consensus(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Confidence + per-scaffold tool sets for audit / UI."""
    viable = [c for c in candidates if isinstance(c, dict)]
    score = agreement_score(viable)
    return {
        "candidates": len(viable),
        "confidence": score,
        "agreement": score,
        "sources": [c.get("scaffold_id") or c.get("source") for c in viable],
        "tools_by_scaffold": {
            (c.get("scaffold_id") or c.get("source") or f"cand{i}"): sorted(
                _tool_names(c)
            )
            for i, c in enumerate(viable)
        },
    }


def merge_tool_lists(
    primary: dict[str, Any], secondary: dict[str, Any], *, max_tools: int = 6
) -> dict[str, Any]:
    """Union tools from two plans (primary order first), capped."""
    seen: set[str] = set()
    tools: list[dict[str, Any]] = []
    for plan in (primary, secondary):
        for entry in plan.get("tools") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("tool") or "")
            if not name or name in seen:
                continue
            seen.add(name)
            tools.append(entry)
            if len(tools) >= max_tools:
                break
        if len(tools) >= max_tools:
            break
    out = dict(primary)
    out["tools"] = tools
    out["stop"] = not bool(tools)
    out["consensus"] = {
        "mode": "merge",
        "sources": [primary.get("scaffold_id"), secondary.get("scaffold_id")],
    }
    return out
