"""Operator-approved custom tool registry: validation, executor, planner wiring."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clean_registry():
    from orchestrator import tools_registry as reg

    def _wipe():
        reg._tools.clear()
        r = reg._redis()
        if r is not None:
            try:
                r.delete(reg.REGISTRY_KEY)
            except Exception:
                pass

    # Isolate each test from Redis/in-proc state.
    _wipe()
    yield
    _wipe()


def test_validate_rejects_bad_name():
    from orchestrator.tools_registry import validate

    with pytest.raises(ValueError):
        validate({"name": "Bad Name", "binary": "ffuf"})


def test_validate_rejects_builtin_collision():
    from orchestrator.tools_registry import validate

    with pytest.raises(ValueError):
        validate({"name": "nmap", "binary": "nmap"})


def test_validate_rejects_shell_interpreter():
    from orchestrator.tools_registry import validate

    with pytest.raises(ValueError):
        validate({"name": "pwn", "binary": "bash", "args_template": ["-c", "{args}"]})


def test_validate_rejects_binary_with_shell_chars():
    from orchestrator.tools_registry import validate

    with pytest.raises(ValueError):
        validate({"name": "pwn", "binary": "ffuf; rm -rf /"})


def test_register_extends_known_tools():
    from orchestrator.mcp.registry import known_tools
    from orchestrator.tools_registry import register_tool

    assert "ffufv2" not in known_tools()
    register_tool(
        {
            "name": "ffufv2",
            "binary": "ffuf",
            "args_template": ["-u", "{target}/FUZZ", "{args}"],
            "description": "custom fuzzer",
            "risk": "medium",
        }
    )
    assert "ffufv2" in known_tools()


def test_render_argv_substitutes_placeholders():
    from orchestrator.tools_registry import render_argv, validate

    rec = validate(
        {
            "name": "webprobe",
            "binary": "curl",
            "args_template": ["-s", "{target}", "--host", "{domain}", "{args}"],
        }
    )
    argv = render_argv(rec, "https://app.example.com/login", ["-v"])
    assert argv == [
        "curl",
        "-s",
        "https://app.example.com/login",
        "--host",
        "app.example.com",
        "-v",
    ]


def test_render_argv_appends_extra_when_no_placeholder():
    from orchestrator.tools_registry import render_argv, validate

    rec = validate({"name": "pinger", "binary": "echo", "args_template": ["hello"]})
    assert render_argv(rec, "t", ["world"]) == ["echo", "hello", "world"]


def test_build_phase_workflow_routes_custom_tool():
    from orchestrator.tasks import run_custom_tool_task
    from orchestrator.tools_registry import register_tool
    from orchestrator import tasks

    register_tool({"name": "webprobe", "binary": "curl", "args_template": ["{target}"]})
    wf = tasks.build_phase_workflow(
        "ai_custom",
        [{"tool": "webprobe", "args": ["-v"]}],
        "example.com",
        parallel=True,
    )
    assert wf is not None
    # group(...) wraps a single signature; confirm it targets the custom executor.
    sig = wf.tasks[0]
    assert sig.task == run_custom_tool_task.name


def test_unknown_tool_still_dropped():
    from orchestrator import tasks

    wf = tasks.build_phase_workflow(
        "ai_custom",
        [{"tool": "does-not-exist", "args": []}],
        "example.com",
        parallel=True,
    )
    assert wf is None


def test_extract_tool_proposal_from_chat():
    from orchestrator.chat.intake import extract_tool_proposal

    text = (
        "Sure, here's a wrapper:\n"
        "```firebreak-tool\n"
        '{"name": "ffufv2", "binary": "ffuf", '
        '"args_template": ["-u", "{target}/FUZZ", "{args}"], '
        '"description": "custom fuzzer", "risk": "medium"}\n'
        "```\nApprove it to enable."
    )
    draft = extract_tool_proposal(text)
    assert draft is not None
    assert draft["name"] == "ffufv2"
    assert draft["binary"] == "ffuf"


def test_extract_tool_proposal_none_when_absent():
    from orchestrator.chat.intake import extract_tool_proposal

    assert extract_tool_proposal("just a normal reply, no tool block") is None
