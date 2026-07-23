"""Chat agent options parsing and config."""

from __future__ import annotations


def test_parse_chat_options_flags_and_attachments():
    from orchestrator.chat.options import parse_chat_options

    opts = parse_chat_options(
        {
            "content": "hello",
            "options": {
                "deep_think": True,
                "web_search": "yes",
                "model": "firebreak",
                "posture": "aggressive",
                "attachments": [
                    {"name": "scan.txt", "content": "open ports: 443", "type": "text/plain"},
                    {"name": "empty.txt", "content": "   "},
                ],
            },
        }
    )
    assert opts.deep_think is True
    assert opts.web_search is True
    assert opts.model == "firebreak"
    assert opts.normalized_posture() == "aggressive"
    assert len(opts.attachments) == 1
    assert opts.attachments[0].name == "scan.txt"


def test_parse_chat_options_ignores_invalid_block():
    from orchestrator.chat.options import parse_chat_options

    opts = parse_chat_options({"options": "not-a-dict"})
    assert opts.deep_think is False
    assert opts.web_search is False
    assert opts.attachments == []


def test_list_chat_models_has_fallback():
    from orchestrator.chat.options import list_chat_models

    models = list_chat_models()
    assert models
    assert all("id" in m and "label" in m for m in models)
