from tools.waf_evasion import (
    evasion_profile,
    obfuscate_payload,
    obfuscate_sql,
    obfuscate_xss,
    random_headers,
)


def test_random_headers_include_user_agent():
    headers = random_headers()
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert headers["User-Agent"]


def test_random_headers_are_safe_for_cli_http_clients():
    for _ in range(20):
        headers = random_headers()
        assert "Connection" not in headers
        assert "Proxy-Connection" not in headers
        assert "Transfer-Encoding" not in headers
        assert not any(k.lower().startswith("sec-") for k in headers)
        encoding = headers.get("Accept-Encoding", "")
        assert encoding != "br"
        assert "br" not in encoding.split(",")


def test_random_headers_merge_extra():
    headers = random_headers({"X-Custom": "1", "Connection": "close"})
    assert headers["X-Custom"] == "1"
    assert "Connection" not in headers


def test_obfuscate_sql_changes_or_keeps_payload():
    payload = "SELECT * FROM users WHERE id=1"
    out = obfuscate_sql(payload)
    assert isinstance(out, str)
    assert len(out) >= len("SELECT")


def test_obfuscate_payload_dispatcher():
    assert isinstance(obfuscate_payload("<script>alert(1)</script>", "xss"), str)
    assert isinstance(obfuscate_payload("cat /etc/passwd", "rce"), str)


def test_evasion_profile_levels():
    low = evasion_profile("low")
    high = evasion_profile("high")
    assert low["random_headers"] is True
    assert high["random_delay_max"] >= low["random_delay_max"]
    cf = evasion_profile("medium", target_waf="cloudflare")
    assert cf["random_delay_max"] >= 1.0
