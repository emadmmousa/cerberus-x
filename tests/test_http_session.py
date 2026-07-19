from unittest.mock import MagicMock, patch

from tools.http_session import EvasiveSession


def test_evasive_session_applies_headers():
    session = EvasiveSession({"random_headers": True})
    assert "User-Agent" in session.session.headers
    session.close()


def test_evasive_session_get_applies_delay():
    with patch("tools.http_session.random_delay") as delay:
        with patch.object(EvasiveSession, "_apply_headers"):
            session = EvasiveSession(
                {"random_headers": False, "random_delay_min": 0.1, "random_delay_max": 0.2}
            )
            session.session = MagicMock()
            session.session.request.return_value = "ok"
            assert session.get("https://example.com") == "ok"
            delay.assert_called_once_with(0.1, 0.2)
            session.close()
