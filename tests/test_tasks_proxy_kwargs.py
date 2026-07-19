from orchestrator.tasks import build_phase_workflow


def test_build_phase_workflow_passes_kwargs_without_secrets():
    wf = build_phase_workflow(
        "exploitation",
        [{"tool": "sqlmap", "args": ["--batch"]}],
        "example.com",
        use_proxy=True,
        proxy_protocol="http",
    )
    assert wf is not None
    text = repr(wf)
    assert "OXYLABS" not in text
    assert "password" not in text.lower()
