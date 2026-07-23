"""Tests for aggressive SQL injection technique catalog and sqlmap strategy."""

from tools import sql_injection as sqli


def test_technique_inventory_covers_major_families():
    inv = sqli.list_techniques()
    assert "union" in inv["classic_inband"]
    assert "time_based" in inv["classic_inband"]
    assert "dns_exfil" in inv["out_of_band"]
    assert "mysql" in inv["database_specific"]
    assert "polyglot" in inv["advanced"]
    assert "bit_by_bit" in inv["blind_refinements"]
    assert "comment_based" in inv["evasion"]
    assert "schema_enum" in inv["data_exfil"]


def test_probe_payloads_include_classic_and_blind():
    payloads = sqli.probe_payloads(dbms=None, count=20)
    blob = " ".join(payloads).upper()
    assert "UNION" in blob or "OR" in blob
    assert any("SLEEP" in p.upper() or "WAITFOR" in p.upper() or "PG_SLEEP" in p.upper() for p in payloads)
    assert any("CONVERT" in p.upper() or "CAST" in p.upper() or "UPDATEXML" in p.upper() for p in payloads)


def test_mysql_specific_and_polyglot():
    mysql = sqli.payloads_for_dbms("mysql")
    assert any("INFORMATION_SCHEMA" in p.upper() or "SLEEP" in p.upper() for p in mysql)
    assert "'" in sqli.POLYGLOT_TRUE or "OR" in sqli.POLYGLOT_TRUE.upper()
    nosql = sqli.nosql_probe_payloads()
    assert any("$ne" in str(p) or "$where" in str(p) or "$regex" in str(p) for p in nosql)


def test_sqli_profile_levels_escalate():
    low = sqli.sqli_profile("low")
    high = sqli.sqli_profile("high")
    agg = sqli.sqli_profile("aggressive", dbms="mysql")
    assert low["level"] <= 2
    assert high["level"] >= low["level"]
    assert agg["risk"] >= 3
    assert "BEUSTQ" in agg["technique"] or set(agg["technique"]) >= set("BEUST")
    assert agg["enumerate"] is True
    assert agg["dump"] is True


def test_build_sqlmap_args_aggressive_includes_techniques_and_enum():
    args = sqli.build_sqlmap_args(
        sqli.sqli_profile("aggressive", dbms="mysql"),
        existing=["--batch", "--forms"],
    )
    joined = " ".join(args)
    assert "--batch" in args
    assert any(a.startswith("--technique=") or a == "--technique" for a in args) or "--technique=BEUSTQ" in joined
    assert "--level=5" in joined or any(a == "--level=5" for a in args)
    assert "--risk=3" in joined or any("risk=3" in a for a in args)
    assert any("current-user" in a or a == "--current-user" for a in args)
    assert any("schema" in a for a in args)
    assert "--dbms=MySQL" in joined or any("MySQL" in a for a in args)


def test_build_sqlmap_args_oob_when_dns_configured(monkeypatch):
    monkeypatch.setenv("FIREBREAK_SQLMAP_DNS_DOMAIN", "exfil.lab.invalid")
    args = sqli.build_sqlmap_args(sqli.sqli_profile("aggressive"))
    assert any("exfil.lab.invalid" in a for a in args)


def test_merge_preserves_user_tamper_and_adds_missing():
    existing = ["--batch", "--level=3", "--tamper=space2comment"]
    out = sqli.build_sqlmap_args(sqli.sqli_profile("high"), existing=existing)
    assert "--tamper=space2comment" in " ".join(out) or any(
        "space2comment" in a for a in out
    )
    # Should not duplicate --batch
    assert out.count("--batch") == 1


def test_follow_on_actions_for_confirmed_sqli():
    actions = sqli.follow_on_sqlmap_actions(dbms="mssql")
    assert len(actions) >= 2
    assert all(a["tool"] == "sqlmap" for a in actions)
    dumpish = " ".join(" ".join(a["args"]) for a in actions)
    assert "--dump" in dumpish or "--schema" in dumpish


def test_next_sqlmap_method_rotates_and_prefers_dbms():
    first = sqli.next_sqlmap_method(tried=set(), dbms="mysql")
    assert first is not None
    assert first["id"] == "mysql_hint"
    second = sqli.next_sqlmap_method(tried={first["id"]}, dbms="mysql")
    assert second is not None
    assert second["id"] != first["id"]
