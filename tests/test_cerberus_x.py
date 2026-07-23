"""Cerberus-X operator persona and triggers."""

from __future__ import annotations


def test_cerberus_routes_tactical_target_through_advisor():
    from orchestrator.chat.cerberus_x import try_cerberus_command

    assert (
        try_cerberus_command(
            "Execute full red team on https://lab.example.com",
            [{"role": "user", "content": "Cerberus begin"}],
        )
        is None
    )

    from orchestrator.chat.cerberus_x import try_cerberus_command

    assert try_cerberus_command("Cerberus start") == "What we making brody?"


def test_cerberus_menu():
    from orchestrator.chat.cerberus_x import CERBERUS_MENU, try_cerberus_command

    reply = try_cerberus_command("Menu")
    assert reply == CERBERUS_MENU
    assert "OSINT" in reply


def test_cerberus_session_active_after_begin_until_reset():
    from orchestrator.chat.cerberus_x import cerberus_session_active

    messages = [
        {"role": "user", "content": "Cerberus begin"},
        {"role": "assistant", "content": "online"},
    ]
    assert cerberus_session_active(messages) is True
    messages.append({"role": "user", "content": "Cerberus reset"})
    assert cerberus_session_active(messages) is False


def test_cerberus_advisor_overlay_includes_playbook():
    from orchestrator.chat.cerberus_x import cerberus_advisor_overlay

    overlay = cerberus_advisor_overlay([{"role": "user", "content": "Cerberus begin"}])
    assert "Cerberus-X persona ACTIVE" in overlay
    assert "scope→tool" in overlay.lower() or "scope → firebreak" in overlay.lower()


def test_advisor_messages_include_cerberus_when_active():
    from orchestrator.chat.intake import _advisor_messages

    rows = _advisor_messages([{"role": "user", "content": "Cerberus begin"}])
    assert "Cerberus-X persona ACTIVE" in rows[0]["content"]


def test_cerberus_status_summarizes_thread():
    from orchestrator.chat.cerberus_x import try_cerberus_command

    messages = [
        {"role": "user", "content": "Cerberus begin"},
        {"role": "user", "content": "Plan recon for app.example.com"},
    ]
    reply = try_cerberus_command("Cerberus status", messages)
    assert reply is not None
    assert "CERBERUS STATUS" in reply
    assert "app.example.com" in reply
