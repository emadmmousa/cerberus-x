"""Chat plan extraction → seed-plan execution for confirmed missions."""

from __future__ import annotations

import pytest


PLAN_TEXT = """
Here's the attack plan for the authorized target.

```firebreak-plan
{"target":"app.example.com","posture":"aggressive","nl_goal":"Web recon then nuclei",
 "phases":[
   {"name":"recon","parallel":true,"tools":[{"tool":"nmap","args":["-sV"]},{"tool":"whatweb","args":["-a","3"]}]},
   {"name":"vuln","parallel":false,"tools":[{"tool":"nuclei","args":["-t","http/cves/"]}]}
 ],
 "new_tools":[
   {"name":"curlprobe","binary":"curl","args_template":["-sI","{target}"],"description":"header probe","risk":"low"}
 ]}
```

Confirm to execute.
"""


def test_extract_execution_plan_parses_phases_and_new_tools():
    from orchestrator.chat.intake import extract_execution_plan

    plan = extract_execution_plan(PLAN_TEXT)
    assert plan is not None
    assert plan["target"] == "app.example.com"
    assert plan["posture"] == "aggressive"
    assert len(plan["phases"]) == 2
    assert plan["phases"][0]["tools"][0]["tool"] == "nmap"
    assert plan["tool_names"] == ["nmap", "whatweb", "nuclei"]
    assert plan["new_tools"][0]["name"] == "curlprobe"


def test_detect_proposal_ready_when_plan_in_reply():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {"role": "user", "content": "Plan an aggressive assess of app.example.com"},
    ]
    proposal = detect_proposal(messages, assistant_reply=PLAN_TEXT)
    assert proposal["ready"] is True
    assert proposal["target"] == "app.example.com"
    assert proposal["plan"]["tool_names"] == ["nmap", "whatweb", "nuclei"]
    assert "nmap" in proposal["nl_goal"] or "execute" in proposal["nl_goal"]


def test_detect_proposal_finds_plan_in_history_on_confirm():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {"role": "user", "content": "Design a chain for app.example.com"},
        {"role": "assistant", "content": PLAN_TEXT},
        {"role": "user", "content": "do it"},
    ]
    proposal = detect_proposal(messages)
    assert proposal["ready"] is True
    assert proposal["plan"]["phases"][0]["name"] == "recon"


def test_run_ai_mission_executes_seed_plan_before_planner(monkeypatch):
    from orchestrator.ai import runner

    calls: list[dict] = []

    class _FakeAsync:
        id = "task-1"

        def successful(self):
            return True

        @property
        def result(self):
            return [{"tool": "nmap", "ports": [{"port": "80"}]}]

        def revoke(self, **_kw):
            return None

        @property
        def children(self):
            return []

    class _FakeWorkflow:
        def apply_async(self):
            return _FakeAsync()

    def fake_build(phase_name, tools, target, **kw):
        calls.append({"phase": phase_name, "tools": [t["tool"] for t in tools]})
        return _FakeWorkflow()

    def boom_planner(*_a, **_k):
        raise AssertionError("planner should not run while seed phases remain")

    monkeypatch.setattr(runner, "build_phase_workflow", fake_build)
    monkeypatch.setattr(runner, "collect_group_results", lambda *_a, **_k: [{"tool": "nmap"}])
    monkeypatch.setattr(runner, "collect_chain_results", lambda *_a, **_k: [{"tool": "nmap"}])
    monkeypatch.setattr(runner, "save_phase_result", lambda *_a, **_k: None)
    monkeypatch.setattr(runner.planner, "suggest_next_phase", boom_planner)

    # Only one seed phase — after it runs, planner would be called; stop via empty.
    def stop_planner(*_a, **_k):
        return {
            "phase_name": "ai_done",
            "reason": "done",
            "parallel": False,
            "stop": True,
            "tools": [],
            "source": "heuristic",
        }

    monkeypatch.setattr(runner.planner, "suggest_next_phase", stop_planner)

    job: dict = {}
    seed = [
        {
            "name": "recon",
            "parallel": True,
            "tools": [{"tool": "nmap", "args": ["-sV"]}],
        }
    ]
    runner.run_ai_mission(
        job=job,
        job_id="job-1",
        target="app.example.com",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        nl_goal="seeded",
        confirm_high_risk=True,
        posture="aggressive",
        seed_plan=seed,
        max_steps=2,
    )
    assert calls, "seed phase should have executed"
    assert calls[0]["tools"] == ["nmap"]
    assert job["ai"]["seeded"] is True
    assert job["ai"]["steps"][0]["source"] == "chat_plan"


def test_compile_plan_from_chat_without_block():
    from orchestrator.chat.intake import compile_plan_from_chat

    messages = [
        {"role": "user", "content": "Let's assess app.example.com"},
        {
            "role": "assistant",
            "content": "I'll run nmap for recon then sqlmap on the login form.",
        },
        {"role": "user", "content": "yes execute the mission"},
    ]
    plan = compile_plan_from_chat(messages)
    assert plan is not None
    assert plan["target"] == "app.example.com"
    assert plan["source"] == "compiled"
    assert "nmap" in plan["tool_names"]
    # sqlmap was named in chat and via the sql keyword.
    assert "sqlmap" in plan["tool_names"]
    assert plan["phases"], "compiled plan must have runnable phases"


def test_detect_proposal_compiles_plan_on_execute_order():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {"role": "user", "content": "Recon and exploit app.example.com aggressively"},
        {"role": "assistant", "content": "Understood. Recommended flow: nmap, nuclei."},
        {"role": "user", "content": "execute the mission based on our chat"},
    ]
    proposal = detect_proposal(messages)
    assert proposal["ready"] is True
    assert proposal["target"] == "app.example.com"
    assert proposal["plan"]["phases"], "must attach a runnable compiled plan"
    assert proposal["posture"] == "aggressive"


def test_detect_proposal_no_target_stays_unready():
    from orchestrator.chat.intake import detect_proposal

    messages = [{"role": "user", "content": "run the mission now"}]
    proposal = detect_proposal(messages)
    assert proposal["ready"] is False
    assert proposal.get("plan") is None


@pytest.fixture(autouse=True)
def _clean_registry():
    from orchestrator import tools_registry as reg

    def wipe():
        reg._tools.clear()
        r = reg._redis()
        if r is not None:
            try:
                r.delete(reg.REGISTRY_KEY)
            except Exception:
                pass

    wipe()
    yield
    wipe()
