"""OSINT seed parsing and authorization helpers."""

from __future__ import annotations

import pytest

from orchestrator.osint.seeds import (
    apply_osint_seeds_to_proposal,
    classify_osint_seed,
    normalize_osint_seeds,
    primary_mission_target,
)


def test_classify_osint_kinds():
    assert classify_osint_seed("person@corp.com")["kind"] == "email"
    assert classify_osint_seed("@alice")["kind"] == "username"
    assert classify_osint_seed("Jane Doe")["kind"] == "full_name"
    assert classify_osint_seed("عبد الباسط هارون جبريل")["kind"] == "full_name"
    assert classify_osint_seed("+1 555 0100")["kind"] == "mobile"
    assert classify_osint_seed("corp.com")["kind"] == "domain"
    assert classify_osint_seed("https://instagram.com/alice")["kind"] == "social_url"


def test_classify_arabic_full_name_with_explicit_kind():
    seed = classify_osint_seed("عبد الباسط هارون جبريل", kind="full_name")
    assert seed["kind"] == "full_name"
    assert seed["value"] == "عبد الباسط هارون جبريل"


def test_normalize_deduplicates_seeds():
    rows = normalize_osint_seeds(
        [
            {"kind": "email", "value": "Person@Corp.com"},
            "person@corp.com",
            {"kind": "username", "value": "@alice"},
        ]
    )
    assert len(rows) == 2
    assert rows[0]["value"] == "person@corp.com"


def test_apply_osint_seeds_to_proposal_sets_target():
    proposal = apply_osint_seeds_to_proposal(
        {"ready": False, "missing": ["target"]},
        [classify_osint_seed("person@corp.com")],
    )
    assert proposal["target"] == "person@corp.com"
    assert proposal["ready"] is True
    assert proposal["osint_seeds"][0]["kind"] == "email"


def test_format_osint_seeds_for_llm_lists_operator_values():
    from orchestrator.osint.seeds import format_osint_seeds_for_llm

    block = format_osint_seeds_for_llm([classify_osint_seed("person@corp.com")])
    assert "person@corp.com" in block
    assert "never invent" in block.lower()


def test_compile_osint_plan_uses_intelligence_tools_only():
    from orchestrator.osint.seeds import compile_osint_plan

    plan = compile_osint_plan(
        [
            classify_osint_seed("Emad Mousa", kind="full_name"),
            classify_osint_seed("+201155664248", kind="mobile"),
        ]
    )
    assert plan is not None
    assert plan["target"] == "Emad Mousa"
    assert plan["tool_names"] == [
        "theharvester",
        "subfinder",
        "gau",
        "sherlock",
        "katana",
        "httpx",
        "whatweb",
        "darkweb",
        "breach_intel",
    ]
    assert all(phase["name"] == "osint" for phase in plan["phases"])


def test_detect_proposal_auto_executes_osint_playbook_with_seeds():
    from orchestrator.chat.intake import detect_proposal

    seeds = [classify_osint_seed("person@corp.com")]
    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only on authorized TARGET and seeds: theharvester, darkweb, breach_intel. "
                "Execute now."
            ),
        }
    ]
    proposal = detect_proposal(
        messages,
        assistant_reply="Starting OSINT sweep.",
        osint_seeds=seeds,
    )
    assert proposal["ready"] is True
    assert proposal["auto_execute"] is True
    assert set(proposal["plan"]["tool_names"]) >= {"theharvester", "darkweb", "breach_intel"}
    assert proposal["osint_seeds"][0]["value"] == "person@corp.com"


def test_primary_osint_mission_target_prefers_full_name():
    from orchestrator.osint.seeds import primary_osint_mission_target

    seeds = [
        classify_osint_seed("https://facebook.com/profile.php"),
        classify_osint_seed("عبد الباسط هارون جبريل", kind="full_name"),
    ]
    assert primary_osint_mission_target(seeds) == "عبد الباسط هارون جبريل"


def test_extract_osint_on_subject_arabic_name():
    from orchestrator.osint.seeds import extract_osint_on_subject

    seeds = extract_osint_on_subject(
        "OSINT-only on عبد الباسط هارون جبريل and seeds: theharvester, darkweb, breach_intel."
    )
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "full_name"
    assert seeds[0]["value"] == "عبد الباسط هارون جبريل"


def test_merge_osint_seeds_for_chat_overrides_full_name_from_prompt():
    from orchestrator.osint.seeds import merge_osint_seeds_for_chat

    merged = merge_osint_seeds_for_chat(
        [classify_osint_seed("Emad Mousa", kind="full_name")],
        "OSINT-only on عبد الباسط هارون جبريل and seeds: theharvester.",
    )
    names = [row["value"] for row in merged if row["kind"] == "full_name"]
    assert names == ["عبد الباسط هارون جبريل"]


def test_extract_followup_prefers_strike_profile_kind():
    from orchestrator.osint.seeds import extract_followup_osint_seeds

    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only on email.\n\n"
                "Target profile for this deck: email (OSINT-only).\n\n"
                "Wait for my next message with the authorized email address before launching."
            ),
        },
        {"role": "user", "content": "person@corp.com"},
    ]
    seeds = extract_followup_osint_seeds("person@corp.com", messages)
    assert seeds == [{"kind": "email", "value": "person@corp.com", "display": "person@corp.com"}]


def test_extract_followup_osint_seeds_after_deck_template():
    from orchestrator.osint.seeds import extract_followup_osint_seeds

    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only: theharvester, darkweb, breach_intel.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": "عبد الباسط هارون جبريل"},
    ]
    seeds = extract_followup_osint_seeds("عبد الباسط هارون جبريل", messages)
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "full_name"
    assert seeds[0]["value"] == "عبد الباسط هارون جبريل"


def test_extract_followup_rejects_launch_ack():
    from orchestrator.osint.seeds import extract_followup_osint_seeds

    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only: theharvester, darkweb, breach_intel.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": "عبدالباسط هارون الشهيبي"},
        {"role": "assistant", "content": "OSINT mission ready. Confirm to proceed."},
        {"role": "user", "content": "Confirmed"},
    ]
    assert extract_followup_osint_seeds("Confirmed", messages) == []
    assert extract_followup_osint_seeds("Yes", messages) == []


def test_resolve_osint_seeds_preserves_target_on_confirm():
    from orchestrator.osint.seeds import resolve_osint_seeds_for_chat

    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only: run the full scrape stack — theharvester, subfinder, gau, "
                "sherlock, katana, httpx, whatweb, darkweb, and breach_intel.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": "عبدالباسط هارون الشهيبي"},
        {"role": "assistant", "content": "OSINT mission ready for عبدالباسط هارون الشهيبي. Confirm to proceed."},
        {"role": "user", "content": "Confirmed"},
    ]
    seeds = resolve_osint_seeds_for_chat([], "Confirmed", messages=messages)
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "full_name"
    assert "الشهيبي" in seeds[0]["value"]
    assert seeds[0]["display"] != "@confirmed"

    seeds_yes = resolve_osint_seeds_for_chat([], "Yes", messages=messages)
    assert len(seeds_yes) == 1
    assert seeds_yes[0]["kind"] == "full_name"
    assert seeds_yes[0]["display"] != "@yes"


def test_resolve_osint_seeds_preserves_target_on_confirm_typo():
    from orchestrator.osint.seeds import resolve_osint_seeds_for_chat

    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only: run theharvester, darkweb, and breach_intel.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {"role": "user", "content": "عبدالباسط هارون الشهيبي"},
        {"role": "assistant", "content": "OSINT mission ready for عبدالباسط هارون الشهيبي. Confirm to proceed."},
        {"role": "user", "content": "Confimed"},
    ]
    seeds = resolve_osint_seeds_for_chat([], "Confimed", messages=messages)
    assert len(seeds) == 1
    assert seeds[0]["kind"] == "full_name"
    assert "الشهيبي" in seeds[0]["value"]
    assert seeds[0]["display"] != "@confimed"


def test_resolve_osint_seeds_ignores_operator_block_when_osint_on_subject():
    from orchestrator.osint.seeds import resolve_osint_seeds_for_chat

    panel = [
        classify_osint_seed("https://facebook.com/profile.php"),
        classify_osint_seed("+201155664248", kind="mobile"),
    ]
    prompt = (
        "OSINT-only on authorized Emad Mousa and seeds: theharvester, darkweb, breach_intel.\n\n"
        "Operator OSINT seeds (use ONLY these — never invent placeholders):\n"
        "- Social profile URL: https://facebook.com/profile.php\n"
        "- Mobile number: +201155664248\n"
        "- Full name: Emad Mousa"
    )
    resolved = resolve_osint_seeds_for_chat(panel, prompt)
    assert len(resolved) == 1
    assert resolved[0]["kind"] == "full_name"
    assert resolved[0]["value"] == "Emad Mousa"


def test_resolve_osint_seeds_prompt_only_ignores_panel():
    from orchestrator.osint.seeds import resolve_osint_seeds_for_chat

    panel = [
        classify_osint_seed("https://facebook.com/profile.php"),
        classify_osint_seed("+201155664248", kind="mobile"),
        classify_osint_seed("Emad Mousa", kind="full_name"),
    ]
    prompt = (
        "OSINT-only on عبد الباسط هارون جبريل and seeds: theharvester, darkweb, breach_intel. "
        "Produce an intelligence report — no port scans or exploitation."
    )
    resolved = resolve_osint_seeds_for_chat(panel, prompt)
    assert len(resolved) == 1
    assert resolved[0]["kind"] == "full_name"
    assert resolved[0]["value"] == "عبد الباسط هارون جبريل"


def test_authorize_chat_targets_scopes_to_prompt_not_panel(tmp_path, monkeypatch):
    from orchestrator.chat.intake import authorize_chat_targets

    path = tmp_path / "authorized_targets.json"
    path.write_text('{"targets":[]}', encoding="utf-8")
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")

    panel = [
        classify_osint_seed("https://facebook.com/profile.php"),
        classify_osint_seed("+201155664248", kind="mobile"),
    ]
    messages = [
        {
            "role": "user",
            "content": (
                "OSINT-only on عبد الباسط هارون جبريل and seeds: theharvester, darkweb, breach_intel."
            ),
        },
        {"role": "user", "content": "add it to my authorized list"},
    ]
    reply, added = authorize_chat_targets(messages=messages, panel_seeds=panel)
    assert len(added) == 1
    assert added[0]["kind"] == "full_name"
    assert "facebook.com" not in reply
    assert "+201155664248" not in reply


def test_apply_osint_seeds_overrides_social_url_for_osint_only():
    proposal = apply_osint_seeds_to_proposal(
        {"target": "https://facebook.com/profile.php", "ready": True},
        [
            classify_osint_seed("https://facebook.com/profile.php"),
            classify_osint_seed("عبد الباسط هارون جبريل", kind="full_name"),
        ],
        osint_only=True,
    )
    assert proposal["target"] == "عبد الباسط هارون جبريل"


def test_primary_mission_target_prefers_domain():
    seeds = [
        classify_osint_seed("person@corp.com"),
        classify_osint_seed("corp.com"),
    ]
    assert primary_mission_target(seeds) == "corp.com"


def test_authorize_chat_targets_adds_missing_seeds(tmp_path, monkeypatch):
    from orchestrator.chat.intake import authorize_chat_targets

    path = tmp_path / "authorized_targets.json"
    path.write_text('{"targets":[]}', encoding="utf-8")
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")

    reply, added = authorize_chat_targets(
        osint_seeds=[classify_osint_seed("https://facebook.com/profile.php")],
    )
    assert added
    assert "Added to your authorized list" in reply


def test_run_intake_enriches_followup_full_name_after_deck_template(monkeypatch):
    import json
    from orchestrator.chat import intake

    history = [
        {
            "role": "user",
            "content": (
                "OSINT-only: theharvester, darkweb, breach_intel.\n\n"
                "Wait for my next message with the authorized target before launching."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "I need a clearer target (hostname or URL) for this authorized mission. "
                "What should we assess?"
            ),
        },
        {"role": "user", "content": "عبد الباسط هارون جبريل"},
    ]
    bad_json = json.dumps(
        {
            "reply": (
                "I need a clearer target (hostname or URL) for this authorized mission. "
                "What should we assess?"
            ),
            "proposal": {
                "target": "",
                "posture": "aggressive",
                "ready": False,
                "missing": ["target"],
            },
        }
    )
    monkeypatch.setattr(intake, "chat_completion", lambda *a, **k: bad_json)
    out = intake.run_intake(history, parse_failures=0, osint_seeds=[])
    assert out["proposal"]["ready"] is True
    assert out["proposal"]["target"] == "عبد الباسط هارون جبريل"
    assert "OSINT mission ready" in out["reply"]


def test_run_intake_deck_template_asks_for_next_target(monkeypatch):
    from orchestrator.chat import intake

    monkeypatch.setattr(intake, "chat_completion", lambda *a, **k: "not-json")
    out = intake.run_intake(
        [
            {
                "role": "user",
                "content": (
                    "OSINT-only: theharvester, darkweb, breach_intel.\n\n"
                    "Wait for my next message with the authorized target before launching."
                ),
            }
        ],
        parse_failures=0,
        osint_seeds=[],
    )
    assert out["proposal"]["ready"] is False
    assert "next message" in out["reply"].lower()
    assert "hostname or URL" not in out["reply"]


def test_authorization_accepts_osint_email(tmp_path, monkeypatch):
    path = tmp_path / "authorized_targets.json"
    path.write_text(
        '{"targets":[{"kind":"email","target":"person@corp.com","value":"person@corp.com","authorized":true}]}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AUTHORIZED_TARGETS_FILE", str(path))
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    from scanner import AuthorizationEnforcer as A

    assert A.check("person@corp.com", kind="email") is True
    assert A.check_seeds([classify_osint_seed("person@corp.com")]) is True
    assert A.check("other@corp.com", kind="email") is False
