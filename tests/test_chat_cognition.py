"""Advisor cognition layer — reasoning guide and situational brief."""

from __future__ import annotations


def test_advisor_system_includes_cognition_guide():
    from orchestrator.chat.cognition import ADVISOR_COGNITION_GUIDE
    from orchestrator.chat.intake import ADVISOR_SYSTEM

    assert ADVISOR_COGNITION_GUIDE in ADVISOR_SYSTEM
    assert "OODA" in ADVISOR_SYSTEM
    assert "Hypothesis stack" in ADVISOR_SYSTEM


def test_build_situation_brief_detects_osint_deck_flow():
    from orchestrator.chat.cognition import build_situation_brief

    messages = [
        {
            "role": "user",
            "content": (
                "Run OSINT only: darkweb, theharvester, breach_intel. "
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": "Jane Doe"},
    ]
    brief = build_situation_brief(messages)
    assert "situation brief" in brief.lower()
    assert "Jane Doe" in brief
    assert "OSINT-only" in brief


def test_advisor_temperature_deep_think_is_point_one():
    from orchestrator.chat.cognition import advisor_temperature
    from orchestrator.chat.options import ChatAgentOptions

    assert advisor_temperature(ChatAgentOptions(deep_think=True)) == 0.1
    assert advisor_temperature(ChatAgentOptions(deep_think=False)) == 0.4


def test_advisor_think_enabled_by_default():
    from orchestrator.chat.cognition import advisor_think_enabled
    from orchestrator.chat.options import ChatAgentOptions

    assert advisor_think_enabled(ChatAgentOptions(deep_think=False)) is True
    assert advisor_think_enabled(ChatAgentOptions(deep_think=True)) is True


def test_advisor_messages_include_think_tags_and_brief():
    from orchestrator.chat.intake import _advisor_messages

    rows = _advisor_messages(
        [{"role": "user", "content": "Plan recon for app.example.com"}],
    )
    system = rows[0]["content"]
    tag = "<" + "think" + ">"
    assert tag in system
    assert "situation brief" in system.lower()


def test_think_block_instruction_uses_hidden_reasoning_tags():
    from orchestrator.chat.cognition import think_block_instruction

    instant = think_block_instruction(deep=False)
    deep = think_block_instruction(deep=True)
    tag = "<" + "think" + ">"
    assert tag in instant
    assert tag in deep
    assert "1–3" in instant or "1-3" in instant
