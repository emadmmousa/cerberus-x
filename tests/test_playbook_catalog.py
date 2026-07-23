"""Playbook catalog + posture mapping tests."""

from orchestrator.playbook_catalog import (
    POSTURE_PLAYBOOKS,
    SPECIALIST_PLAYBOOKS,
    list_playbooks,
    list_specialist_playbooks,
    playbook_for_posture,
    render_hardening_markdown,
    specialist_playbook,
)


def test_playbook_for_posture_mapping():
    assert playbook_for_posture("balanced").endswith("balanced_offense_defense.yaml")
    assert playbook_for_posture("aggressive").endswith("complete_dark_arsenal.yaml")
    assert playbook_for_posture("defensive").endswith("defensive_audit.yaml")
    assert playbook_for_posture("blue") == POSTURE_PLAYBOOKS["defensive"]


def test_list_playbooks_includes_recommended():
    rows = list_playbooks()
    assert len(rows) >= 3
    paths = {r["path"] for r in rows}
    assert "playbooks/balanced_offense_defense.yaml" in paths
    assert "playbooks/defensive_audit.yaml" in paths
    bal = next(r for r in rows if r["id"] == "balanced_offense_defense")
    assert "balanced" in bal["recommended_for"]


def test_render_hardening_markdown():
    md = render_hardening_markdown(
        "lab.example",
        [{"title": "Harden SSH", "detail": "Disable password auth", "severity": "high"}],
        posture="defensive",
        job_id="job-1",
    )
    assert "# Hardening report — lab.example" in md
    assert "Harden SSH" in md
    assert "job-1" in md


def test_specialist_playbooks_registered():
    assert specialist_playbook("advanced_web_recon") == SPECIALIST_PLAYBOOKS["advanced_web_recon"]
    rows = list_specialist_playbooks()
    ids = {row["id"] for row in rows}
    assert "sqli_recon_chain" in ids
    assert "xss_hunt_chain" in ids
    assert all(row["phase_count"] >= 3 for row in rows)
