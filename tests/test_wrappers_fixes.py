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


def test_nmap_sqlmap_nuclei_ffuf_url_helpers():
    assert nmap._host("https://wks.agency/x") == "wks.agency"
    assert sqlmap._url("wks.agency") == "https://wks.agency"
    assert nuclei._url("wks.agency") == "https://wks.agency"
    assert ffuf._url("wks.agency") == "https://wks.agency"


def test_hydra_requires_explicit_service_and_arguments():
    result = hydra.scan("lab.example")

    assert result["error"] == "hydra requires an explicit service and arguments"


def test_hydra_builds_command_with_normalized_target(monkeypatch):
    calls = []

    def fake_check_output(command, **kwargs):
        calls.append((command, kwargs))
        return "Hydra finished"

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)

    result = hydra.scan(
        "ssh://lab.example:22/path",
        ["ssh", "-l", "operator", "-P", "/tmp/lab-passwords.txt", "-t", "1"],
    )

    assert calls == [
        (
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
            ],
            {"stderr": subprocess.STDOUT, "text": True},
        )
    ]
    assert result == {
        "tool": "hydra",
        "target": "lab.example",
        "service": "ssh",
        "raw_output": "Hydra finished",
    }


def test_hydra_reports_missing_binary(monkeypatch):
    def missing_binary(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "check_output", missing_binary)

    result = hydra.scan("lab.example", ["ssh", "-l", "operator", "-p", "test"])

    assert result["error"] == "hydra binary not found"
