"""Target normalization + auto-execute mission flow."""

from __future__ import annotations


def test_normalize_engagement_target_variants():
    from orchestrator.chat.targets import is_web_engagement_target, normalize_engagement_target

    ctx = normalize_engagement_target("https://www.wks.agency/path")
    assert ctx["host"] == "wks.agency"
    assert ctx["https_url"].startswith("https://")
    assert "https://www.wks.agency" in ctx["variants"]
    assert "http://wks.agency" in ctx["variants"]
    assert "wks.agency" in ctx["variants"]


def test_normalize_engagement_target_skips_osint_full_name():
    from orchestrator.chat.targets import is_web_engagement_target, normalize_engagement_target

    name = "عبد الباسط هارون جبريل"
    assert is_web_engagement_target(name) is False
    assert normalize_engagement_target(name) == {}


def test_resolve_launch_plan_keeps_osint_full_name():
    from orchestrator.api import chat_missions as cm
    from orchestrator.osint.seeds import classify_osint_seed

    name = "عبد الباسط هارون جبريل"
    seeds = [classify_osint_seed(name, kind="full_name")]
    draft = {
        "ready": True,
        "target": name,
        "osint_seeds": seeds,
        "plan": {
            "phases": [
                {
                    "name": "osint",
                    "parallel": True,
                    "tools": [{"tool": "theharvester", "args": ["-b", "crtsh"]}],
                }
            ],
            "tool_names": ["theharvester", "darkweb", "breach_intel"],
        },
    }
    _plan, target, *_rest = cm._resolve_launch_plan({}, {}, draft)
    assert target == name


def test_detect_proposal_auto_execute_on_order():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {
            "role": "user",
            "content": "Plan and execute a full red-team process for https://www.wks.agency",
        },
    ]
    proposal = detect_proposal(messages, assistant_reply="Running recon first.")
    assert proposal["ready"] is True
    assert proposal["target"] == "wks.agency"
    assert proposal.get("auto_execute") is True
    assert proposal["plan"]["phases"]


def test_auto_run_off_suppresses_auto_execute():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {
            "role": "user",
            "content": "Plan and execute a full red-team process for https://www.wks.agency",
        },
    ]
    # Same execute-intent order, but operator disabled Auto Run → confirm required.
    proposal = detect_proposal(
        messages, assistant_reply="Running recon first.", auto_run=False
    )
    assert proposal["ready"] is True
    assert proposal.get("auto_execute") is False


def test_always_run_promotes_plan_only_request():
    from orchestrator.chat.intake import detect_proposal

    # Plan-only phrasing normally shows a confirm card (auto_execute False)…
    messages = [
        {"role": "user", "content": "Design an attack chain for https://www.wks.agency"}
    ]
    plain = detect_proposal(messages, assistant_reply="Here is a plan.")
    assert plain["ready"] is True
    assert plain.get("auto_execute") is False

    # …but Always Run auto-launches it.
    promoted = detect_proposal(
        messages, assistant_reply="Here is a plan.", always_run=True
    )
    assert promoted["ready"] is True
    assert promoted.get("auto_execute") is True


def test_always_run_requires_auto_run():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {"role": "user", "content": "Design an attack chain for https://www.wks.agency"}
    ]
    # always_run cannot override an explicit auto_run=False kill.
    proposal = detect_proposal(
        messages, assistant_reply="Here is a plan.", auto_run=False, always_run=True
    )
    assert proposal["ready"] is True
    assert proposal.get("auto_execute") is False


def test_auto_run_default_preserves_execute_behavior():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {"role": "user", "content": "Execute the plan against https://www.wks.agency now"}
    ]
    # No auto_run kwarg → defaults on → unchanged auto-launch behavior.
    proposal = detect_proposal(messages, assistant_reply="Launching.")
    assert proposal.get("auto_execute") is True


def test_parse_chat_options_auto_run_defaults_and_overrides():
    from orchestrator.chat.options import parse_chat_options

    # Defaults: auto_run on, always_run off.
    defaults = parse_chat_options({})
    assert defaults.auto_run is True
    assert defaults.always_run is False

    overridden = parse_chat_options(
        {"options": {"auto_run": False, "always_run": True}}
    )
    assert overridden.auto_run is False
    assert overridden.always_run is True
    assert overridden.as_dict()["auto_run"] is False
    assert overridden.as_dict()["always_run"] is True


def test_detect_proposal_hunt_until_vulns_auto_launches():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {
            "role": "user",
            "content": (
                "Find vulnerabilities on wks.agency — don't stop until you find something"
            ),
        },
    ]
    proposal = detect_proposal(messages, assistant_reply="Starting recon.")
    assert proposal["ready"] is True
    assert proposal["target"] == "wks.agency"
    assert proposal.get("auto_execute") is True
    assert proposal.get("until_vulns") is True
    assert proposal["plan"]["until_vulns"] is True
    assert "nuclei" in proposal["plan"]["tool_names"]


def test_finalize_execution_plan_hydrates_placeholders():
    from orchestrator.chat.intake import finalize_execution_plan

    plan = finalize_execution_plan(
        {
            "target": "http://www.example.com",
            "phases": [
                {
                    "name": "probe",
                    "parallel": False,
                    "tools": [{"tool": "curlprobe", "args": ["-sI", "{url}"]}],
                }
            ],
            "new_tools": [],
        }
    )
    args = plan["phases"][0]["tools"][0]["args"]
    assert args[1].startswith("https://")
    assert "example.com" in args[1]


def test_register_plan_tools_invents_missing(monkeypatch):
    from orchestrator.api import chat_missions as cm

    registered = []

    def fake_register(raw, **kwargs):
        registered.append(raw["name"])
        return {"name": raw["name"], "binary": raw["binary"], "args_template": raw["args_template"]}

    monkeypatch.setattr("orchestrator.tools_registry.register_tool", fake_register)
    monkeypatch.setattr("orchestrator.tools_registry.get_tool", lambda _n: None)
    monkeypatch.setattr(
        "orchestrator.tools_registry.invent_tool",
        lambda name, **kwargs: {
            "name": name,
            "binary": name,
            "args_template": ["{url}"],
            "description": "test",
            "risk": "low",
        },
    )

    names = cm._register_plan_tools(
        {
            "phases": [{"name": "x", "parallel": False, "tools": [{"tool": "curlprobe", "args": []}]}],
            "new_tools": [
                {
                    "name": "curlprobe",
                    "binary": "curl",
                    "args_template": ["-sI", "{url}"],
                    "description": "header probe",
                    "risk": "low",
                }
            ],
        },
        created_by="tester",
        org_id="org",
        chat_id="chat-1",
    )
    assert names == ["curlprobe"]


def test_run_ai_mission_hunt_stops_on_vuln_found(monkeypatch):
    from orchestrator.ai import runner

    calls: list[str] = []

    class _FakeAsync:
        id = "task-1"

        def successful(self):
            return True

        @property
        def result(self):
            return [
                {
                    "tool": "nuclei",
                    "findings": [
                        {"severity": "high", "title": "Test CVE", "template_id": "CVE-2024-0001"}
                    ],
                }
            ]

        def revoke(self, **_kw):
            return None

        @property
        def children(self):
            return []

    class _FakeWorkflow:
        def apply_async(self):
            return _FakeAsync()

    def fake_build(phase_name, tools, target, **kw):
        calls.extend(t["tool"] for t in tools)
        return _FakeWorkflow()

    monkeypatch.setattr(runner, "build_phase_workflow", fake_build)
    monkeypatch.setattr(
        runner,
        "collect_chain_results",
        lambda *_a, **_k: [
            {
                "tool": "nuclei",
                "findings": [
                    {"severity": "high", "title": "Test CVE", "template_id": "CVE-2024-0001"}
                ],
            }
        ],
    )
    monkeypatch.setattr(runner, "collect_group_results", runner.collect_chain_results)
    monkeypatch.setattr(runner, "save_phase_result", lambda *_a, **_k: None)
    monkeypatch.setattr(runner, "_run_post_phase_actions", lambda **_kw: None)

    job: dict = {}
    runner.run_ai_mission(
        job=job,
        job_id="job-hunt",
        target="app.example.com",
        use_proxy=False,
        proxy_protocol="http",
        evasion={},
        nl_goal="Hunt vulnerabilities on app.example.com until confirmed findings",
        confirm_high_risk=True,
        posture="aggressive",
        until_vulns=True,
        max_steps=2,
    )
    assert calls, "hunt should execute at least one tool phase"
    assert job["ai"]["vuln_found"] is True
    assert job["ai"]["until_vulns"] is True
