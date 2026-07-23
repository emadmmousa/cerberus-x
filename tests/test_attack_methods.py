"""Attack method catalog tests."""

from __future__ import annotations


def test_full_tool_rotation_covers_catalog():
    from tools.attack_methods import FULL_TOOL_ROTATION, METHOD_CATALOG
    from tools.inventory import CLI_TOOL_CATALOG, TOOL_CATALOG

    catalog_tools = {e["name"] for e in TOOL_CATALOG}
    cli_tools = {e["name"] for e in CLI_TOOL_CATALOG}
    method_tools = {
        t for m in METHOD_CATALOG for t in (m.get("tools") or [])
    }
    # Every method tool is a known catalog entry (CLI wrappers or scaffold bundles).
    assert method_tools <= catalog_tools
    # Rotation covers exactly the atomic CLI wrappers; scaffold/* bundles run as
    # grouped strikes, not part of the single-tool rotation.
    assert set(FULL_TOOL_ROTATION) == cli_tools


def test_next_rotation_tool_skips_tried():
    from tools.attack_methods import next_rotation_tool

    allow = {"nmap", "nuclei", "sqlmap"}
    assert next_rotation_tool(allow, tried=set(), failed=set()) == "nmap"
    assert next_rotation_tool(allow, tried={"nmap"}, failed=set()) == "nuclei"
    assert next_rotation_tool(allow, tried={"nmap", "nuclei"}, failed=set()) == "sqlmap"
    assert next_rotation_tool(allow, tried=allow, failed=set()) is None


def test_defensive_posture_filters_high_risk_methods():
    from tools.attack_methods import list_methods

    aggressive = {m["id"] for m in list_methods(posture="aggressive")}
    defensive = {m["id"] for m in list_methods(posture="defensive")}
    assert "sqli_full" in aggressive
    assert "sqli_full" not in defensive
    assert "port_sweep" in defensive


def test_compile_aggressive_phases_respects_allowlist():
    from tools.attack_methods import compile_aggressive_phases

    allow = {"nmap", "nuclei", "sqlmap"}
    phases = compile_aggressive_phases(allow)
    names = {p["name"] for p in phases}
    assert "recon" in names
    assert "vuln" in names
    assert "exploit" in names
    all_tools = {t["tool"] for p in phases for t in p["tools"]}
    assert all_tools <= allow


def test_aggressive_args_for_sqlmap():
    from tools.attack_methods import aggressive_args_for

    args = aggressive_args_for("sqlmap")
    joined = " ".join(args)
    assert "--technique=BEUSTQ" in joined
    assert "--level=5" in joined


def test_compile_plan_includes_full_arsenal_on_adaptive():
    from orchestrator.chat.intake import compile_plan_from_chat

    plan = compile_plan_from_chat(
        [{"role": "user", "content": "Execute full red-team on app.example.com"}]
    )
    assert plan is not None
    tools = plan.get("tool_names") or []
    assert "nuclei" in tools
    assert "sqlmap" in tools
    assert "metasploit" in tools
    assert "darkweb" in tools


def test_wants_database_access_from_goal_and_signals():
    from tools.attack_methods import wants_database_access

    assert wants_database_access("get into the mysql database")
    assert wants_database_access(
        "assess target",
        profile={"signals": ["sqli", "login"]},
        decision_state={"sql_injection": True},
    )


def test_next_db_access_phase_rotates_sqlmap_profiles():
    from tools.attack_methods import next_db_access_phase

    plan = next_db_access_phase(
        allow={"sqlmap", "nuclei", "ffuf"},
        tried_methods=set(),
        failed_tools={"sqlmap"},
        dbms="postgres",
        step=2,
    )
    assert plan is not None
    assert plan["source"] == "db_access_rotation"
    assert plan["tools"][0]["tool"] == "sqlmap"
    assert "--dbms=PostgreSQL" in " ".join(plan["tools"][0]["args"])
