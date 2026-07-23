"""Mission chat intent detection — plan, launch, confirm, execute synonyms."""

from __future__ import annotations

import pytest

from orchestrator.chat.intent import (
    is_launch_ack_message,
    mission_auto_execute_trigger,
    mission_compile_trigger,
    wants_confirm,
    wants_execution,
    wants_launch,
    wants_plan,
)


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "Confirmed",
        "go ahead",
        "sounds good",
        "let's go",
        "affirmative",
        "green light",
        "نعم",
        "موافق",
    ],
)
def test_launch_ack_synonyms(text: str):
    assert is_launch_ack_message(text)


@pytest.mark.parametrize(
    "text",
    [
        "go to example.com",
        "attack surface on app.example.com",
        "Confirmed user @alice",
    ],
)
def test_launch_ack_rejects_casual_non_confirm(text: str):
    assert not is_launch_ack_message(text)


@pytest.mark.parametrize("text", ["great", "fine", "go", "start"])
def test_launch_ack_rejects_casual_non_confirm(text: str):
    assert not is_launch_ack_message(text)


@pytest.mark.parametrize(
    "text",
    [
        "carry out the plan for app.example.com",
        "put it into action",
        "run what we discussed",
        "based on our conversation execute now",
        "get started on the assessment",
    ],
)
def test_execute_synonyms(text: str):
    assert wants_execution(text, [{"role": "user", "content": text}])


@pytest.mark.parametrize(
    "text",
    [
        "conduct recon on app.example.com",
        "perform a scan of app.example.com",
        "kick off assessment for app.example.com",
        "probe app.example.com",
    ],
)
def test_launch_synonyms(text: str):
    assert wants_launch(text)


@pytest.mark.parametrize(
    "text",
    [
        "design an attack chain for app.example.com",
        "outline the approach for app.example.com",
        "what's the strategy for app.example.com",
        "map out a mission against app.example.com",
    ],
)
def test_plan_synonyms(text: str):
    assert wants_plan(text, [{"role": "user", "content": text}])


def test_plan_only_compiles_without_auto_execute():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {
            "role": "user",
            "content": "Design an attack chain for app.example.com",
        },
    ]
    proposal = detect_proposal(messages, assistant_reply="I'll map recon then nuclei.")
    assert proposal["ready"] is True
    assert proposal["target"] == "app.example.com"
    assert proposal.get("plan")
    assert proposal.get("auto_execute") is not True


def test_sounds_good_confirm_auto_executes_osint_thread():
    from orchestrator.chat.intake import detect_proposal

    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only: theharvester, darkweb, breach_intel.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": "Jane Doe"},
        {"role": "assistant", "content": "OSINT mission ready for Jane Doe. Confirm to proceed."},
        {"role": "user", "content": "sounds good"},
    ]
    proposal = detect_proposal(messages)
    assert proposal["ready"] is True
    assert proposal["target"] == "Jane Doe"
    assert proposal.get("auto_execute") is True


def test_osint_for_subject_phrasing():
    from orchestrator.osint.seeds import extract_osint_on_subject

    seeds = extract_osint_on_subject("Run OSINT for Jane Doe using theharvester and darkweb.")
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "full_name"
    assert seeds[0]["value"] == "Jane Doe"


def test_advisor_system_includes_intent_guide():
    from orchestrator.chat.intake import ADVISOR_SYSTEM
    from orchestrator.chat.intent import ADVISOR_INTENT_GUIDE

    assert ADVISOR_INTENT_GUIDE in ADVISOR_SYSTEM
    assert "sounds good" in ADVISOR_SYSTEM
    assert "plan-only" in ADVISOR_SYSTEM.lower() or "PLAN-ONLY" in ADVISOR_SYSTEM
    assert "نعم" in ADVISOR_SYSTEM


def test_mission_compile_trigger_includes_plan_not_execute_only():
    assert mission_compile_trigger("outline a plan for app.example.com", None)
    assert not mission_auto_execute_trigger("outline a plan for app.example.com", None)
    assert mission_auto_execute_trigger("go ahead and run it", None)


@pytest.mark.parametrize(
    "text",
    [
        "Confimed",
        "Comfirmed",
        "Confirm",
        "confirmmed",
    ],
)
def test_launch_ack_typo_synonyms(text: str):
    assert is_launch_ack_message(text)


def test_detect_proposal_osint_confirm_typo_keeps_full_name_target():
    from orchestrator.chat.intake import detect_proposal

    name = "عبد الباسط هارون الشهيبي"
    messages = [
        {
            "role": "user",
            "content": (
                "Run OSINT only: darkweb --method full, theharvester, and breach_intel. "
                "Scrape public/hidden sources and report leak matches. "
                "Do not run vuln scans or exploitation.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": name},
        {
            "role": "assistant",
            "content": f"OSINT mission ready for {name}. Confirm to proceed.",
        },
        {"role": "user", "content": "Confimed"},
    ]
    proposal = detect_proposal(messages)
    assert proposal["ready"] is True
    assert proposal.get("auto_execute") is True
    assert "الشهيبي" in proposal["target"]
    assert proposal["target"] != "@confimed"
    assert proposal["target"] != "@confirmed"
    assert proposal.get("osint_seeds")
    assert proposal["osint_seeds"][0]["kind"] == "full_name"


def test_classify_osint_seed_rejects_confirm_typo():
    from orchestrator.osint.seeds import classify_osint_seed

    with pytest.raises(ValueError, match="launch ack"):
        classify_osint_seed("Confimed")
