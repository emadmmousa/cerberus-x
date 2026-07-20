from tools.waf_evasion import (
    apply_encoding_chain,
    build_evasion_headers,
    character_duplicate,
    dual_url_and_body,
    evasion_profile,
    fragment_across_request,
    generate_payload_variants,
    html_entity_encode,
    list_techniques,
    multipart_form,
    obfuscate_path,
    obfuscate_payload,
    obfuscate_sql,
    pad_body_for_size_limit,
    pollute_params,
    random_headers,
    reorder_headers,
    sqlmap_tamper_for_evasion,
    url_encode,
    utf8_overlong_encode_path,
    waf_specific_profile,
    whitelist_probe_urls,
    with_static_extension,
    wrap_json_payload,
)


def test_random_headers_include_user_agent():
    headers = random_headers()
    assert "User-Agent" in headers
    assert "Accept" in headers
    assert headers["User-Agent"]


def test_random_headers_are_safe_for_cli_http_clients():
    for _ in range(20):
        headers = random_headers(
            evasion={
                "level": "aggressive",
                "random_headers": True,
                "header_injection": True,
            }
        )
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


def test_aggressive_headers_include_injection():
    headers = build_evasion_headers(
        {
            "level": "aggressive",
            "random_headers": True,
            "header_injection": True,
            "header_injection_aggressive": True,
            "trusted_user_agent": True,
            "header_reorder": True,
        },
        target="https://lab.example/admin",
    )
    assert "X-Forwarded-For" in headers
    assert "X-Original-URL" in headers
    assert "X-Rewrite-URL" in headers


def test_obfuscate_sql_changes_or_keeps_payload():
    payload = "SELECT * FROM users WHERE id=1"
    out = obfuscate_sql(payload)
    assert isinstance(out, str)
    assert len(out) >= len("SELECT")


def test_encoding_chain_and_variants():
    assert "%" in url_encode("'", 1)
    assert "&lt;" in html_entity_encode("<script>")
    assert "%c0%ae" in utf8_overlong_encode_path("../etc/passwd")
    chained = apply_encoding_chain("OR 1=1", ["mixed_case", "comments"])
    assert isinstance(chained, str)
    variants = generate_payload_variants("' OR 1=1--", "sql", count=4)
    assert len(variants) >= 2
    assert "ee" in character_duplicate("select", "e")


def test_obfuscate_payload_dispatcher():
    assert isinstance(obfuscate_payload("<script>alert(1)</script>", "xss"), str)
    assert isinstance(obfuscate_payload("cat /etc/passwd", "rce"), str)
    assert isinstance(obfuscate_path("../../etc/passwd"), str)


def test_parameter_pollution_and_static_ext():
    pairs = pollute_params({}, "q", "safe", "payload", style="last_wins")
    assert pairs[0] == ("q", "safe")
    assert pairs[-1] == ("q", "payload")
    assert with_static_extension("https://x.test/admin").endswith(
        (".jpg", ".png", ".gif", ".css", ".js", ".woff", ".ico", ".svg")
    )
    ctype, body = multipart_form({"q": "1' OR '1'='1"})
    assert "multipart/form-data" in ctype
    assert "1' OR '1'='1" in body
    frag = fragment_across_request("q", "ABCDEF")
    assert "params" in frag and "data" in frag and "headers" in frag
    dual = dual_url_and_body("q", "x")
    assert dual["params"]["q"] == dual["data"]["q"]
    assert '"q":' in wrap_json_payload("q", "a\"b")
    assert len(pad_body_for_size_limit("hi", 100)) >= 100
    assert any("/admin" in u for u in whitelist_probe_urls("https://t.example"))
    shuffled = reorder_headers({"A": "1", "B": "2", "C": "3"})
    assert set(shuffled) == {"A", "B", "C"}


def test_evasion_profile_levels():
    low = evasion_profile("low")
    high = evasion_profile("high")
    aggressive = evasion_profile("aggressive", target_waf="cloudflare")
    assert low["random_headers"] is True
    assert high["random_delay_max"] >= low["random_delay_max"]
    assert aggressive["header_injection"] is True
    assert aggressive["trusted_user_agent"] is True
    assert aggressive["multipart"] is True
    assert aggressive["ai_payloads"] is True
    assert "space2comment" in sqlmap_tamper_for_evasion(aggressive)
    cf = evasion_profile("medium", target_waf="cloudflare")
    assert cf["random_delay_max"] >= 1.0


def test_waf_specific_and_inventory():
    assert "sqlmap_tampers" in waf_specific_profile("ModSecurity CRS")
    inventory = list_techniques()
    assert "encoding_obfuscation" in inventory
    assert "url_triple" in inventory["encoding_obfuscation"]
    assert "multipart" in inventory["parameters"]
    assert "ai_adversarial_payload" in inventory["advanced"]
    assert "raw_chunked_smuggling" in inventory["not_implemented_protocol"]
