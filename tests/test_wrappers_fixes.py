import subprocess

from tools.wrappers import (
    ffuf,
    gobuster,
    hydra,
    masscan,
    nmap,
    nuclei,
    rustscan,
    sqlmap,
)


def test_gobuster_length_from_error():
    msg = (
        "Error: the server returns a status code that matches the provided options "
        "for non existing urls. https://example.com/uuid => 403 (Length: 650). "
        "To continue please exclude the status code or the length"
    )
    assert gobuster._length_from_error(msg) == 650


def test_gobuster_with_exclude_length_replaces_previous():
    args = ["dir", "-u", "https://x", "--exclude-length", "1", "-q"]
    assert gobuster._with_exclude_length(args, 650) == [
        "dir",
        "-u",
        "https://x",
        "-q",
        "--exclude-length",
        "650",
    ]


def test_rustscan_host_strips_url():
    assert rustscan._host("https://wks.agency/path") == "wks.agency"
    assert rustscan._host("wks.agency") == "wks.agency"


def test_masscan_extract_host():
    assert masscan._extract_host("https://wks.agency:443/x") == "wks.agency"


def test_masscan_parse_port_list():
    assert masscan._ports_from_args(["-p80,443,22", "--rate=1000"]) == [80, 443, 22]
    assert masscan._ports_from_args(["-p", "80,443"]) == [80, 443]
    assert masscan._ports_from_args(["-p1-3"]) == [1, 2, 3]


def test_masscan_tcp_connect_fallback(monkeypatch):
    monkeypatch.setattr(masscan, "_resolve_target", lambda host: "1.2.3.4")
    monkeypatch.setattr(
        masscan,
        "_run_masscan_syn",
        lambda *a, **k: ("", []),
    )
    monkeypatch.setattr(
        masscan,
        "_tcp_connect_ports",
        lambda address, ports, timeout=2.0: [
            {"port": "80", "protocol": "tcp"},
            {"port": "443", "protocol": "tcp"},
        ],
    )

    result = masscan.scan("example.com", ["-p80,443", "--rate=1000"])

    assert "error" not in result
    assert result["ports"] == [
        {"port": "80", "protocol": "tcp"},
        {"port": "443", "protocol": "tcp"},
    ]
    assert result["method"] == "tcp-connect-fallback"
    assert "fallback" in result["raw_output"].lower()


def test_masscan_prefers_syn_results(monkeypatch):
    monkeypatch.setattr(masscan, "_resolve_target", lambda host: "1.2.3.4")
    monkeypatch.setattr(
        masscan,
        "_run_masscan_syn",
        lambda *a, **k: (
            "Discovered open port 443/tcp on 1.2.3.4\n",
            [{"port": "443", "protocol": "tcp"}],
        ),
    )

    called = {"fallback": False}

    def boom(*a, **k):
        called["fallback"] = True
        return []

    monkeypatch.setattr(masscan, "_tcp_connect_ports", boom)

    result = masscan.scan("example.com", ["-p443", "--rate=1000"])

    assert called["fallback"] is False
    assert result["method"] == "syn"
    assert result["ports"] == [{"port": "443", "protocol": "tcp"}]


def test_nmap_sqlmap_nuclei_ffuf_url_helpers():
    assert nmap._host("https://wks.agency/x") == "wks.agency"
    assert sqlmap._url("wks.agency") == "https://wks.agency"
    assert nuclei._url("wks.agency") == "https://wks.agency"
    assert ffuf._url("wks.agency") == "https://wks.agency"


def test_hydra_default_args_target_only(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "[DATA] attacking ssh://lab.example:22/\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(hydra, "_default_wordlist", lambda: "/tmp/passes.txt")

    result = hydra.scan("lab.example")

    assert "error" not in result
    assert result["service"] == "ssh"
    assert calls[0][:3] == ["hydra", "-l", "admin"]
    assert calls[0][-2:] == ["lab.example", "ssh"]
    assert "-P" in calls[0]


def test_hydra_builds_command_with_normalized_target(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "Hydra finished"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = hydra.scan(
        "ssh://lab.example:22/path",
        ["ssh", "-l", "operator", "-P", "/tmp/lab-passwords.txt", "-t", "1"],
    )

    assert calls == [
        [
            "hydra",
            "-l",
            "operator",
            "-P",
            "/tmp/lab-passwords.txt",
            "-t",
            "1",
            "lab.example",
            "ssh",
        ]
    ]
    assert result["raw_output"] == "Hydra finished"
    assert "error" not in result


def test_hydra_accepts_native_service_url_args(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = hydra.scan(
        "takwene.com",
        ["-l", "admin", "-P", "/tmp/passes.txt", "ssh://takwene.com"],
    )

    assert calls[0] == [
        "hydra",
        "-l",
        "admin",
        "-P",
        "/tmp/passes.txt",
        "ssh://takwene.com",
    ]
    assert result["service"] == "ssh"


def test_hydra_reports_missing_binary(monkeypatch):
    def missing_binary(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing_binary)

    result = hydra.scan("lab.example", ["ssh", "-l", "operator", "-p", "test"])

    assert result["error"] == "hydra binary not found"


def test_zmap_host_and_ports():
    from tools.wrappers import zmap

    assert zmap._host("https://takwene.com/x") == "takwene.com"
    assert zmap._ports_from_args(["-p", "80,443"]) == [80, 443]


def test_nikto_and_xsstrike_url_helpers():
    from tools.wrappers import nikto, xsstrike

    assert nikto._url("takwene.com") == "https://takwene.com"
    assert xsstrike._url("takwene.com").startswith("https://takwene.com")
    assert "?q=test" in xsstrike._url("takwene.com")


def test_impacket_and_cme_host_helpers():
    from tools.wrappers import impacket, crackmapexec

    assert impacket._host("smb://lab.example/share") == "lab.example"
    assert crackmapexec._host("https://lab.example") == "lab.example"


def test_rustscan_ensures_address_after_flag():
    assert rustscan._ensure_address(["-a", "--ulimit", "5000"], "takwene.com") == [
        "-a",
        "takwene.com",
        "--ulimit",
        "5000",
    ]
    assert rustscan._ensure_address(["--ulimit", "5000", "--top"], "takwene.com") == [
        "-a",
        "takwene.com",
        "--ulimit",
        "5000",
        "--top",
    ]


def test_rustscan_parses_open_host_port_lines():
    output = "Open 34.72.42.51:80\nOpen 34.72.42.51:443\nOpen 34.72.42.51:22\n"
    assert rustscan._parse_ports(output) == [
        {"port": "80", "state": "open"},
        {"port": "443", "state": "open"},
        {"port": "22", "state": "open"},
    ]


def test_ffuf_parses_status_lines_with_spaces():
    output = (
        "Documents and Settings  [Status: 301, Size: 168, Words: 11, Lines: 2]\n"
        "Program Files           [Status: 301, Size: 159, Words: 10, Lines: 2]\n"
    )
    assert ffuf._parse_results(output) == [
        {"path": "Documents and Settings", "status": "301", "size": "168"},
        {"path": "Program Files", "status": "301", "size": "159"},
    ]


def test_nikto_drops_port_when_url_host_used():
    from tools.wrappers import nikto

    assert nikto._normalize_args(
        "https://takwene.com",
        ["-ssl", "-port", "443", "-maxtime", "60"],
    ) == ["-maxtime", "60"]


def test_hydra_normalizes_nested_target_url():
    host, service, command = hydra._build_command(
        "https://takwene.com",
        ["-l", "admin", "-P", "/tmp/pass.txt", "ssh://https://takwene.com"],
    )
    assert host == "takwene.com"
    assert service == "ssh"
    assert command[-1] == "ssh://takwene.com"


def test_gobuster_status_from_error_and_blacklist():
    msg = (
        "Error: the server returns a status code that matches the provided options "
        "for non existing urls. https://example.com/uuid => 301 (Length: 182). "
        "To continue please exclude the status code or the length"
    )
    assert gobuster._status_from_error(msg) == "301"
    assert gobuster._with_blacklist_status(["dir", "-u", "https://x", "-b", "404"], "301") == [
        "dir",
        "-u",
        "https://x",
        "-b",
        "301,404",
    ]


def test_nuclei_resolves_short_template_paths(tmp_path, monkeypatch):
    root = tmp_path / "nuclei-templates"
    (root / "http" / "cves").mkdir(parents=True)
    monkeypatch.setattr(nuclei, "TEMPLATE_ROOTS", (str(root),))
    assert nuclei._resolve_template_arg("cves/").rstrip("/") == str(root / "http" / "cves")
    assert nuclei._normalize_args(["-t", "cves/", "-severity", "high"]) == [
        "-t",
        nuclei._resolve_template_arg("cves/"),
        "-severity",
        "high",
    ]


def test_ffuf_rewrites_common_wordlist_aliases():
    args = ffuf._normalize_args(
        ["-u", "{{target}}/FUZZ", "-w", "/usr/share/wordlists/dirb/common.txt"],
        "https://takwene.com",
    )
    assert args[1] == "https://takwene.com/FUZZ"
    assert args[3] == "/usr/share/dirb/wordlists/common.txt"
    assert "-ac" in args


def test_ffuf_custom_args_receive_a_runtime_limit():
    args = ffuf._normalize_args(
        ["-u", "{{target}}/FUZZ", "-w", "/tmp/words.txt"],
        "https://takwene.com",
    )
    assert args[args.index("-maxtime") + 1] == "60"


def test_crackmapexec_strips_url_target_args():
    from tools.wrappers import crackmapexec

    assert crackmapexec._normalize_args(
        ["smb", "https://takwene.com", "-u", "admin", "-p", "password"],
        "takwene.com",
    ) == ["smb", "takwene.com", "-u", "admin", "-p", "password"]
