from orchestrator.tasks import build_phase_workflow


def test_build_phase_workflow_normalizes_empty_metasploit_args():
    wf = build_phase_workflow(
        "test",
        [{"tool": "metasploit", "args": []}],
        "example.com",
    )
    link = wf.tasks[0]
    assert link.args[1][0] == "auxiliary/scanner/portscan/tcp"


def test_build_phase_workflow_normalizes_gobuster_shorthand():
    wf = build_phase_workflow(
        "test",
        [{"tool": "gobuster", "args": []}],
        "https://example.com",
    )
    link = wf.tasks[0]
    args = link.args[1]
    assert args[0] == "dir"
    assert "-w" in args
