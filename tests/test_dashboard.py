from pathlib import Path

from orchestrator.dashboard import STATIC_APP, app


def test_dashboard_serves_spa_when_built():
    client = app.test_client()
    spa_index = STATIC_APP / "index.html"

    response = client.get("/")

    assert response.status_code == 200
    if spa_index.is_file():
        html = response.get_data(as_text=True)
        assert 'id="root"' in html
        assert "CERBERUS" in html.upper()
    else:
        # Fallback Jinja template during development without a frontend build
        html = response.get_data(as_text=True)
        assert "CERBERUS" in html.upper()
