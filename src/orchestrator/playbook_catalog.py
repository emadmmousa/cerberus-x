"""Playbook catalog helpers for Firebreak dual-mode missions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from orchestrator.ai.posture import Posture, normalize_posture

PLAYBOOKS_DIR = Path(__file__).resolve().parents[2] / "playbooks"

# Recommended YAML playbook per posture (non-AI runs).
POSTURE_PLAYBOOKS: dict[Posture, str] = {
    "balanced": "playbooks/balanced_offense_defense.yaml",
    "aggressive": "playbooks/complete_dark_arsenal.yaml",
    "defensive": "playbooks/defensive_audit.yaml",
}


def list_playbooks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not PLAYBOOKS_DIR.is_dir():
        return rows
    for path in sorted(PLAYBOOKS_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        phases = data.get("phases") or data.get("steps") or []
        rel = f"playbooks/{path.name}"
        postures = [
            p for p, rec in POSTURE_PLAYBOOKS.items() if rec.endswith(path.name)
        ]
        rows.append(
            {
                "id": path.stem,
                "path": rel,
                "name": data.get("name") or path.stem,
                "description": (data.get("description") or "").strip(),
                "phase_count": len(phases) if isinstance(phases, list) else 0,
                "evasion": data.get("evasion"),
                "recommended_for": postures,
            }
        )
    return rows


def playbook_for_posture(posture: str | None) -> str:
    return POSTURE_PLAYBOOKS[normalize_posture(posture)]


def render_hardening_markdown(
    target: str,
    recommendations: list[dict[str, str]],
    *,
    posture: str = "balanced",
    job_id: str | None = None,
) -> str:
    lines = [
        f"# Hardening report — {target}",
        "",
        f"- Posture: `{posture}`",
    ]
    if job_id:
        lines.append(f"- Mission: `{job_id}`")
    lines.extend(["", "## Recommendations", ""])
    if not recommendations:
        lines.append("_No recommendations generated._")
        return "\n".join(lines) + "\n"
    for i, row in enumerate(recommendations, 1):
        sev = row.get("severity") or "info"
        lines.append(f"{i}. **{row.get('title', 'Item')}** ({sev})")
        lines.append(f"   - {row.get('detail', '')}")
        lines.append("")
    return "\n".join(lines)
