"""Adaptive target study and invention tests."""

from __future__ import annotations


def test_tool_result_failed_detects_errors():
    from orchestrator.ai.target_study import tool_result_failed, tool_result_productive

    assert tool_result_failed({"tool": "nuclei", "error": "timeout"})
    assert not tool_result_productive({"tool": "nuclei", "error": "timeout"})
    assert tool_result_productive(
        {"tool": "nuclei", "findings": [{"severity": "high", "title": "x"}]}
    )


def test_phase_tool_outcomes_marks_failures():
    from orchestrator.ai.target_study import phase_tool_outcomes

    outcomes = phase_tool_outcomes(
        [{"tool": "ffuf"}, {"tool": "nuclei"}],
        [
            {"tool": "ffuf", "error": "stalled"},
            {"tool": "nuclei", "findings": [{"severity": "medium", "title": "y"}]},
        ],
    )
    assert outcomes["ffuf"] == "failed"
    assert outcomes["nuclei"] == "success"


def test_recommend_attack_tools_prefers_wordpress_stack():
    from orchestrator.ai.target_study import recommend_attack_tools

    tools = recommend_attack_tools(
        {"signals": ["wordpress", "web"], "http_open": True},
        {"nuclei", "nikto", "gobuster", "nmap"},
        tried={"nmap"},
        failed={"nikto"},
    )
    assert tools[0] == "nuclei"
    assert "nikto" not in tools


def test_build_surface_study_phase_includes_variants():
    from orchestrator.ai.target_study import build_surface_study_phase

    phase = build_surface_study_phase(
        {
            "https_url": "https://example.com",
            "https_www": "https://www.example.com",
            "variants": ["https://example.com", "http://example.com"],
        },
        {"whatweb", "curlprobe"},
    )
    assert phase is not None
    assert phase["name"] == "surface_study"
    assert len(phase["tools"]) >= 2


def test_invent_novel_attack_plan_fallback(monkeypatch):
    from orchestrator.ai.invention import invent_novel_attack_plan

    monkeypatch.setattr(
        "orchestrator.ai.llm.llm_configured",
        lambda: False,
    )
    plan = invent_novel_attack_plan(
        "example.com",
        "Find a way in",
        profile={"signals": ["cloudflare", "web"], "http_open": True},
        failed_tools={"nuclei", "ffuf", "gobuster"},
        tried_tools={"nuclei", "ffuf", "gobuster", "nmap"},
        decision_state={"http_open": True},
        step=1,
    )
    assert plan is not None
    assert plan["source"] == "novel_invention"
    assert plan["new_tools"][0]["binary"] == "curl"
    assert plan["tools"][0]["tool"] == plan["new_tools"][0]["name"]


def test_adaptive_escalation_uses_profile_before_invention(monkeypatch):
    from orchestrator.ai import runner

    monkeypatch.setattr(
        runner,
        "_profile_escalation_plan",
        lambda *a, **k: {
            "phase_name": "profile_nuclei",
            "reason": "test",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": "nuclei", "args": []}],
            "source": "profile_escalation",
        },
    )
    plan = runner._adaptive_escalation_plan(
        "example.com",
        "assess",
        job={},
        completed_tools={"nmap"},
        failed_tools={"ffuf"},
        step=2,
        posture="aggressive",
        profile={"signals": ["web"], "http_open": True},
        decision_state={},
        inventions_used=0,
    )
    assert plan["source"] == "profile_escalation"


def test_db_access_rotation_runs_before_profile_escalation(monkeypatch):
    from orchestrator.ai import runner

    monkeypatch.setattr(
        runner,
        "_profile_escalation_plan",
        lambda *a, **k: {
            "phase_name": "profile_nuclei",
            "reason": "test",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": "nuclei", "args": []}],
            "source": "profile_escalation",
        },
    )
    job: dict = {}
    plan = runner._adaptive_escalation_plan(
        "example.com",
        "get into the database on app.example.com",
        job=job,
        completed_tools={"sqlmap"},
        failed_tools={"sqlmap"},
        step=4,
        posture="aggressive",
        profile={"signals": ["sqli", "login", "web"], "http_open": True},
        decision_state={"sql_injection": True},
        inventions_used=0,
    )
    assert plan["source"] == "db_access_rotation"
    assert plan["tools"][0]["tool"] == "sqlmap"
    assert job["ai"]["db_methods_tried"]


def test_invent_novel_db_fallback(monkeypatch):
    from orchestrator.ai.invention import invent_novel_attack_plan

    monkeypatch.setattr("orchestrator.ai.llm.llm_configured", lambda: False)
    plan = invent_novel_attack_plan(
        "example.com",
        "get into the database",
        profile={"signals": ["login", "web"], "http_open": True},
        failed_tools={"sqlmap", "nuclei"},
        tried_tools={"sqlmap", "nuclei", "ffuf"},
        decision_state={"http_open": True},
        step=2,
    )
    assert plan is not None
    assert "SQLi" in plan["reason"] or "SQLi" in plan["new_tools"][0]["description"]


def test_wants_adaptive_attack_on_execute_order():
    from orchestrator.chat.intake import wants_adaptive_attack

    assert wants_adaptive_attack(
        "Plan and execute a full red-team process for app.example.com",
        [{"role": "user", "content": "Plan and execute a full red-team process for app.example.com"}],
    )


def test_compile_plan_includes_surface_study():
    from orchestrator.chat.intake import compile_plan_from_chat

    plan = compile_plan_from_chat(
        [{"role": "user", "content": "Execute full assessment of app.example.com"}]
    )
    assert plan is not None
    phase_names = [p["name"] for p in plan["phases"]]
    assert "surface_study" in phase_names
    assert plan.get("adaptive_attack") is True
