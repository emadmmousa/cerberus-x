"""Dark web OSINT method tests."""

from __future__ import annotations


def test_list_dark_web_methods():
    from tools.dark_web import list_dark_web_methods

    inv = list_dark_web_methods()
    assert "discovery" in inv
    assert "onion_search" in inv["discovery"]
    assert "leak_hunt" in inv["leak_intel"]


def test_parse_method_args():
    from tools.dark_web import parse_method_args

    assert parse_method_args(["--method", "leak_hunt"]) == "leak_hunt"
    assert parse_method_args(["--method=onion_search"]) == "onion_search"
    assert parse_method_args(["full"]) == "full"
    assert parse_method_args(None) == "full"


def test_run_onion_search_without_network(monkeypatch):
    from tools import dark_web as dw

    def fake_get(url, timeout=25, via_tor=False):
        return 200, "visit abcdefghijklmnop.onion for leaks"

    monkeypatch.setattr(dw, "_http_get", fake_get)
    result = dw.run_dark_web_method("onion_search", "example.com")
    assert "abcdefghijklmnop.onion" in result.get("onions", [])
    assert result.get("productive") is True


def test_onion_probe_skips_without_tor(monkeypatch):
    from tools import dark_web as dw

    monkeypatch.setattr(dw, "tor_socks_url", lambda: None)
    monkeypatch.setattr(
        dw,
        "_run_index_searches",
        lambda method, domain, seeds=None: {
            "method": method,
            "onions": ["abcdefghijklmnop.onion"],
            "hits": [],
            "productive": True,
        },
    )
    result = dw.run_dark_web_method("onion_probe", "example.com")
    assert result.get("probes")
    assert result["probes"][0].get("skipped") is True


def test_darkweb_wrapper_scan_parses_osint_seeds(monkeypatch):
    from tools.wrappers import darkweb as wrapper

    monkeypatch.setattr(wrapper, "dark_web_enabled", lambda: True)
    monkeypatch.setattr(
        wrapper,
        "run_dark_web_method",
        lambda method, target, seeds=None: {
            "method": method,
            "target": target,
            "seeds": seeds or [],
            "productive": True,
        },
    )
    result = wrapper.scan("عبد الباسط هارون جبريل", ["--method", "leak_hunt"])
    assert result["tool"] == "darkweb"
    assert result["seeds"][0]["kind"] == "full_name"


def test_theharvester_strips_seeds_and_skips_full_name(monkeypatch):
    from tools.wrappers import theharvester as wrapper

    def fail_run(*args, **kwargs):
        raise AssertionError("theHarvester CLI should not run for full-name-only seeds")

    monkeypatch.setattr(wrapper.subprocess, "check_output", fail_run)
    seeds_json = '[{"kind":"full_name","value":"عبد الباسط هارون جبريل","display":"عبد الباسط هارون جبريل"}]'
    result = wrapper.scan(
        "عبد الباسط هارون جبريل",
        ["-b", "crtsh", "--seeds", seeds_json],
    )
    assert result["skipped"] is True
    assert result["productive"] is False
    assert "sherlock" in result["note"]


def test_theharvester_uses_email_domain_from_seeds(monkeypatch):
    from tools.wrappers import theharvester as wrapper

    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return "Emails found:\nuser@corp.com"

    monkeypatch.setattr(wrapper.subprocess, "check_output", fake_run)
    seeds_json = '[{"kind":"email","value":"user@corp.com","display":"user@corp.com"}]'
    result = wrapper.scan(
        "عبد الباسط هارون جبريل",
        ["-b", "crtsh", "--seeds", seeds_json],
    )
    assert "-d" in captured["cmd"]
    assert "corp.com" in captured["cmd"]
    assert result["productive"] is True


def test_darkweb_wrapper_registered():
    from orchestrator.tasks import _TASK_MAP
    from tools.inventory import catalog_by_name

    assert "darkweb" in _TASK_MAP
    assert "darkweb" in catalog_by_name()


def test_attack_methods_include_dark_web():
    from tools.attack_methods import FULL_TOOL_ROTATION, list_methods

    assert "darkweb" in FULL_TOOL_ROTATION
    ids = {m["id"] for m in list_methods(posture="aggressive")}
    assert "darkweb_leak_hunt" in ids
