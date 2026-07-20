from tools.wrappers import theharvester


def test_scan_filters_banner_email_and_target_host(monkeypatch):
    banner = """
*******************************************************************
* cmartorella@edge-security.com                                   *
*******************************************************************
[*] Target: takwene.com
[*] No hosts found.
takwene.com
"""

    monkeypatch.setattr(theharvester, "_command", lambda: ["theHarvester"])
    monkeypatch.setattr(
        theharvester.subprocess,
        "check_output",
        lambda *a, **k: banner,
    )
    result = theharvester.scan("https://takwene.com")
    assert result["emails"] == []
    assert result["hosts"] == []
    assert result["target"] == "takwene.com"
