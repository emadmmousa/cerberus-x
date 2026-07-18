import pytest

from tools.metasploit_rpc import MetasploitRpcError
from tools.wrappers import metasploit


class FakeClient:
    def __init__(self, *, module_options=None, execution_result=None, error=None):
        self.options_response = module_options or {}
        self.execution_result = execution_result or {}
        self.error = error
        self.option_calls = []
        self.execute_calls = []

    def module_options(self, module_type, module_name):
        self.option_calls.append((module_type, module_name))
        if self.error:
            raise self.error
        return self.options_response

    def execute_module(self, module_type, module_name, options):
        self.execute_calls.append((module_type, module_name, options))
        if self.error:
            raise self.error
        return self.execution_result


def install_client(monkeypatch, client):
    monkeypatch.setattr(metasploit, "MetasploitRpcClient", lambda: client)


def test_scan_parses_full_module_path_and_coerces_options(monkeypatch):
    client = FakeClient(
        module_options={
            "RHOSTS": {"required": True},
            "THREADS": {"required": False},
            "VERBOSE": {"required": False},
            "LABEL": {"required": False},
        },
        execution_result={"job_id": 7, "uuid": "run-abc"},
    )
    install_client(monkeypatch, client)

    result = metasploit.scan(
        "https://scanner.example.test:8443/path",
        [
            "auxiliary/scanner/portscan/tcp",
            "THREADS=10",
            "VERBOSE=true",
            "LABEL=internal",
        ],
    )

    assert client.option_calls == [("auxiliary", "scanner/portscan/tcp")]
    assert client.execute_calls == [
        (
            "auxiliary",
            "scanner/portscan/tcp",
            {
                "RHOSTS": "scanner.example.test",
                "THREADS": 10,
                "VERBOSE": True,
                "LABEL": "internal",
            },
        )
    ]
    assert result == {
        "tool": "metasploit",
        "target": "https://scanner.example.test:8443/path",
        "module": "auxiliary/scanner/portscan/tcp",
        "job_id": 7,
        "uuid": "run-abc",
        "response": {"job_id": 7, "uuid": "run-abc"},
    }


def test_scan_preserves_explicit_rhosts_and_coerces_false_and_negative_int(
    monkeypatch,
):
    client = FakeClient(
        module_options={"RHOSTS": {"required": True}},
        execution_result={"job_id": None, "uuid": "run-def"},
    )
    install_client(monkeypatch, client)

    metasploit.scan(
        "https://ignored.example.test/path",
        [
            "auxiliary/scanner/portscan/tcp",
            "RHOSTS=10.0.0.0/24",
            "SSL=false",
            "TIMEOUT=-1",
        ],
    )

    assert client.execute_calls[0][2] == {
        "RHOSTS": "10.0.0.0/24",
        "SSL": False,
        "TIMEOUT": -1,
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([], "module path is required"),
        (["portscan"], "full module path"),
        (["auxiliary/"], "full module path"),
        (["/scanner/portscan/tcp"], "full module path"),
        (
            ["auxiliary/scanner/portscan/tcp", "THREADS"],
            "KEY=VALUE",
        ),
        (
            ["auxiliary/scanner/portscan/tcp", "=10"],
            "option key",
        ),
    ],
)
def test_scan_returns_structured_errors_for_malformed_arguments(args, message):
    result = metasploit.scan("example.test", args)

    assert result["tool"] == "metasploit"
    assert result["target"] == "example.test"
    assert result["code"] == "invalid_arguments"
    assert message in result["error"]


def test_scan_reports_all_missing_required_options_without_executing(monkeypatch):
    client = FakeClient(
        module_options={
            "RHOSTS": {"required": True},
            "RPORT": {"required": True, "default": 80},
            "USERNAME": {"required": True},
            "PASSWORD": {"required": True},
        }
    )
    install_client(monkeypatch, client)

    result = metasploit.scan(
        "example.test",
        ["auxiliary/scanner/http/example", "USERNAME="],
    )

    assert result == {
        "tool": "metasploit",
        "target": "example.test",
        "module": "auxiliary/scanner/http/example",
        "code": "missing_required_options",
        "error": "Missing required module options: PASSWORD, USERNAME",
    }
    assert client.execute_calls == []


def test_scan_returns_safe_structured_rpc_errors(monkeypatch):
    client = FakeClient(error=MetasploitRpcError("RPC service unavailable"))
    install_client(monkeypatch, client)

    result = metasploit.scan(
        "example.test",
        ["auxiliary/scanner/portscan/tcp"],
    )

    assert result == {
        "tool": "metasploit",
        "target": "example.test",
        "module": "auxiliary/scanner/portscan/tcp",
        "code": "rpc_error",
        "error": "RPC service unavailable",
    }


def test_scan_rejects_non_mapping_module_options_response(monkeypatch):
    client = FakeClient(module_options=["unexpected"])
    install_client(monkeypatch, client)

    result = metasploit.scan(
        "example.test",
        ["auxiliary/scanner/portscan/tcp"],
    )

    assert result["code"] == "rpc_error"
    assert result["error"] == "Metasploit RPC returned invalid module options"
    assert client.execute_calls == []


@pytest.mark.parametrize(
    ("target", "expected_rhosts"),
    [
        ("https://scanner.example.test:8443/path", "scanner.example.test"),
        ("http://[2001:db8::1]:8443/path", "2001:db8::1"),
        ("10.0.0.0/24", "10.0.0.0/24"),
        ("2001:db8::/32", "2001:db8::/32"),
        ("192.168.1.10:8080", "192.168.1.10"),
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        ("scanner.example.test", "scanner.example.test"),
        ("192.168.1.10", "192.168.1.10"),
    ],
)
def test_host_derives_rhosts_from_urls_cidrs_and_host_ports(target, expected_rhosts):
    assert metasploit._host(target) == expected_rhosts


def test_scan_derives_rhosts_from_ipv4_cidr_target(monkeypatch):
    client = FakeClient(
        module_options={"RHOSTS": {"required": True}},
        execution_result={"job_id": 1, "uuid": "cidr"},
    )
    install_client(monkeypatch, client)

    metasploit.scan("10.0.0.0/24", ["auxiliary/scanner/portscan/tcp"])

    assert client.execute_calls[0][2]["RHOSTS"] == "10.0.0.0/24"


def test_celery_metasploit_signature_is_json_serializable_and_status_is_generic():
    import inspect
    import json

    from orchestrator.tasks import run_metasploit_task

    signature = run_metasploit_task.si(
        "https://scanner.example.test",
        ["auxiliary/scanner/portscan/tcp", "THREADS=10"],
    )
    payload = dict(signature)
    json.dumps(payload)
    assert payload["args"] == (
        "https://scanner.example.test",
        ["auxiliary/scanner/portscan/tcp", "THREADS=10"],
    )

    source = inspect.getsource(run_metasploit_task.run)
    assert "Metasploit module" in source
    assert "auxiliary scan" not in source
