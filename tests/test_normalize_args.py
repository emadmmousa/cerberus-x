import pytest

from tools.normalize_args import default_args_for, normalize_tool_args
from tools.wrappers.metasploit import DEFAULT_MODULE


def test_empty_args_receive_defaults():
    nmap_args = normalize_tool_args("nmap", "example.com", [])
    assert "-sV" in nmap_args
    assert "-T4" in nmap_args
    assert normalize_tool_args("metasploit", "example.com", []) == [DEFAULT_MODULE]


def test_metasploit_shorthand_normalized():
    args = normalize_tool_args("metasploit", "10.0.0.1", ["portscan"])
    assert args[0] == DEFAULT_MODULE


def test_metasploit_invalid_module_falls_back():
    args = normalize_tool_args("metasploit", "10.0.0.1", ["not-a-real-module-name"])
    assert args[0] == DEFAULT_MODULE


def test_masscan_drops_foreign_flags():
    args = normalize_tool_args(
        "masscan", "example.com", ["-sV", "-p80,443", "--rate=1000"]
    )
    assert "-sV" not in args
    assert any(str(a).startswith("-p") for a in args)


def test_nmap_fixes_bad_port_spec():
    args = normalize_tool_args("nmap", "https://evil/80", ["-sV", "-p", "https://evil/80"])
    assert "https://evil/80" not in args
    assert "-p" in args


def test_gobuster_injects_mode_and_wordlist():
    args = normalize_tool_args("gobuster", "https://example.com", ["-u", "https://x"])
    assert args[0] == "dir"
    assert "-w" in args
    assert "-u" in args


def test_nuclei_rewrites_template_flag():
    args = normalize_tool_args(
        "nuclei", "https://example.com", ["-template", "cves/", "-severity", "high"]
    )
    assert "-t" in args
    assert "-template" not in args


def test_ffuf_injects_url_and_wordlist():
    args = normalize_tool_args("ffuf", "example.com", ["-ac"])
    assert "-u" in args
    assert any("example.com" in str(a) for a in args)
    assert "-w" in args


def test_theharvester_injects_domain():
    args = normalize_tool_args("theharvester", "https://example.com/path", ["-b", "crtsh"])
    assert args[:2] == ["-d", "example.com"]


def test_sqlmap_ensures_batch():
    args = normalize_tool_args("sqlmap", "https://example.com", ["--forms"])
    assert args[0] == "--batch"


def test_rustscan_ensures_address():
    args = normalize_tool_args("rustscan", "scanme.nmap.org", ["--top"])
    assert "-a" in args
    idx = args.index("-a")
    assert args[idx + 1] == "scanme.nmap.org"
    assert "--no-banner" in args


def test_crackmapexec_empty_gets_smb_probe():
    args = normalize_tool_args("crackmapexec", "10.0.0.5", [])
    assert args[0] == "smb"
    assert "10.0.0.5" in args


def test_impacket_empty_gets_host():
    args = normalize_tool_args("impacket", "https://dc.corp.local", [])
    assert args == ["dc.corp.local"]


def test_target_placeholder_replaced():
    args = normalize_tool_args("nmap", "target.test", ["-p", "{{target}}"])
    assert "{{target}}" not in " ".join(args)


@pytest.mark.parametrize(
    "tool",
    [
        "nmap",
        "gobuster",
        "nuclei",
        "ffuf",
        "metasploit",
        "masscan",
        "nikto",
        "sqlmap",
        "theharvester",
        "rustscan",
    ],
)
def test_all_common_tools_normalize_empty_args(tool):
    args = normalize_tool_args(tool, "example.com", [])
    assert isinstance(args, list)
    assert len(args) > 0 or tool in {"hydra", "impacket", "crackmapexec"}


def test_phase_timeout_longer_for_proof_of_impact(monkeypatch):
    from orchestrator.ai.runner import (
        IMPACT_PHASE_TIMEOUT_SECONDS,
        PHASE_TIMEOUT_SECONDS,
        VULN_PHASE_TIMEOUT_SECONDS,
        _phase_timeout_seconds,
    )

    monkeypatch.delenv("FIREBREAK_PHASE_TIMEOUT", raising=False)
    monkeypatch.delenv("FIREBREAK_VULN_PHASE_TIMEOUT", raising=False)
    monkeypatch.delenv("FIREBREAK_IMPACT_PHASE_TIMEOUT", raising=False)

    assert _phase_timeout_seconds("proof_of_impact_s3", [{"tool": "sqlmap"}]) >= 240
    assert _phase_timeout_seconds("proof_of_impact_s3", [{"tool": "sqlmap"}]) == IMPACT_PHASE_TIMEOUT_SECONDS
    gobuster_timeout = _phase_timeout_seconds("discovery", [{"tool": "gobuster"}])
    assert gobuster_timeout >= PHASE_TIMEOUT_SECONDS
    assert gobuster_timeout >= VULN_PHASE_TIMEOUT_SECONDS
