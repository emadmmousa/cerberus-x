from orchestrator.dashboard import app


def test_dashboard_renders_metasploit_controls():
    client = app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Metasploit Modules" in html
    assert "Interactive Console" in html
    assert 'id="searchModulesBtn"' in html
    assert 'id="runModuleBtn"' in html
    assert 'id="refreshJobsBtn"' in html
    assert 'id="refreshSessionsBtn"' in html
    assert 'id="consoleOpenBtn"' in html
    assert "msf_console_create" in html
    assert "textContent" in html
    assert "innerHTML" not in html
