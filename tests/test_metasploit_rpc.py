import json

import pytest
import requests

from tools.metasploit_rpc import (
    MetasploitRpcAuthError,
    MetasploitRpcClient,
    MetasploitRpcConfig,
    MetasploitRpcConfigError,
    MetasploitRpcConnectionError,
    MetasploitRpcError,
    MetasploitRpcTimeoutError,
)

import msgpack


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.content = msgpack.packb(payload, use_bin_type=True)
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def unpack_call(fake_session, index):
    return msgpack.unpackb(fake_session.calls[index][1]["data"], raw=False)


def make_client(*outcomes, **config_overrides):
    config = MetasploitRpcConfig(
        host=config_overrides.pop("host", "metasploit"),
        port=config_overrides.pop("port", 55553),
        username=config_overrides.pop("username", "msf"),
        password=config_overrides.pop("password", "top-secret"),
        ssl=config_overrides.pop("ssl", False),
        timeout=config_overrides.pop("timeout", 2.5),
        retries=config_overrides.pop("retries", 0),
        retry_delay=config_overrides.pop("retry_delay", 0),
        **config_overrides,
    )
    session = FakeSession(*outcomes)
    return MetasploitRpcClient(config, session=session), session


def test_config_reads_environment(monkeypatch):
    monkeypatch.setenv("MSF_RPC_HOST", "rpc.internal")
    monkeypatch.setenv("MSF_RPC_PORT", "55554")
    monkeypatch.setenv("MSF_RPC_USER", "operator")
    monkeypatch.setenv("MSF_RPC_PASSWORD", "generated-secret")
    monkeypatch.setenv("MSF_RPC_SSL", "true")
    monkeypatch.setenv("MSF_RPC_VERIFY_SSL", "true")
    monkeypatch.setenv("MSF_RPC_TIMEOUT", "7.5")
    monkeypatch.setenv("MSF_RPC_RETRIES", "4")
    monkeypatch.setenv("MSF_RPC_RETRY_DELAY", "0.25")

    config = MetasploitRpcConfig.from_env()

    assert config == MetasploitRpcConfig(
        host="rpc.internal",
        port=55554,
        username="operator",
        password="generated-secret",
        ssl=True,
        verify_ssl=True,
        timeout=7.5,
        retries=4,
        retry_delay=0.25,
    )
def test_config_requires_password(monkeypatch):
    monkeypatch.delenv("MSF_RPC_PASSWORD", raising=False)

    with pytest.raises(MetasploitRpcConfigError, match="MSF_RPC_PASSWORD"):
        MetasploitRpcConfig.from_env()


def test_call_authenticates_and_attaches_token():
    client, session = make_client(
        FakeResponse({b"result": b"success", b"token": b"rpc-token"}),
        FakeResponse({b"version": b"6.4.0"}),
    )

    result = client.call("core.version")

    assert result == {"version": "6.4.0"}
    assert unpack_call(session, 0) == ["auth.login", "msf", "top-secret"]
    assert unpack_call(session, 1) == ["core.version", "rpc-token"]
    assert session.calls[0][0] == "http://metasploit:55553/api/"
    assert session.calls[0][1]["headers"] == {
        "Content-Type": "binary/message-pack"
    }
    assert session.calls[0][1]["timeout"] == 2.5
    assert session.calls[0][1]["verify"] is False


def test_ssl_selects_https_endpoint():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"version": "6.4.0"}),
        ssl=True,
    )

    client.call("core.version")

    assert session.calls[0][0] == "https://metasploit:55553/api/"


def test_ssl_verification_can_be_enabled(monkeypatch):
    monkeypatch.setenv("MSF_RPC_PASSWORD", "top-secret")
    monkeypatch.setenv("MSF_RPC_SSL", "true")
    monkeypatch.setenv("MSF_RPC_VERIFY_SSL", "true")
    session = FakeSession(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"version": "6.4.0"}),
    )
    client = MetasploitRpcClient(session=session)

    client.call("core.version")

    assert session.calls[0][1]["verify"] is True


def test_nested_byte_values_are_normalized_to_json_safe_values():
    client, _ = make_client(
        FakeResponse({b"result": b"success", b"token": b"token"}),
        FakeResponse(
            {
                b"items": [{b"name": b"scanner", b"raw": b"\xff"}],
                b"pair": (b"one", b"two"),
            }
        ),
    )

    result = client.call("module.search", "scanner")

    assert result == {
        "items": [{"name": "scanner", "raw": "\ufffd"}],
        "pair": ["one", "two"],
    }
    json.dumps(result)


def test_authentication_failure_raises_safe_typed_error():
    client, _ = make_client(
        FakeResponse({b"result": b"failure", b"error_message": b"bad top-secret"})
    )

    with pytest.raises(MetasploitRpcAuthError) as exc_info:
        client.call("core.version")

    assert "top-secret" not in str(exc_info.value)
    assert "rpc-token" not in str(exc_info.value)


def test_rpc_failure_raises_safe_typed_error():
    client, _ = make_client(
        FakeResponse({"result": "success", "token": "rpc-token"}),
        FakeResponse({"error": True, "error_message": "failed with rpc-token"}),
    )

    with pytest.raises(MetasploitRpcError) as exc_info:
        client.call("module.info", "auxiliary", "missing")

    assert str(exc_info.value) == "failed with [REDACTED]"
    assert "rpc-token" not in str(exc_info.value)
    assert "top-secret" not in str(exc_info.value)
    assert exc_info.value.method == "module.info"


def test_rpc_failure_preserves_non_secret_error_message():
    client, _ = make_client(
        FakeResponse({"result": "success", "token": "rpc-token"}),
        FakeResponse({"error": True, "error_message": "Unknown module type"}),
    )

    with pytest.raises(MetasploitRpcError, match="Unknown module type"):
        client.call("module.info", "invalid", "missing")


def test_invalid_token_reauthenticates_once_and_retries_call():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "old-token"}),
        FakeResponse(
            {"error": True, "error_message": "Invalid Authentication Token"}
        ),
        FakeResponse({"result": "success", "token": "new-token"}),
        FakeResponse({"version": "6.4.0"}),
    )

    assert client.call("core.version") == {"version": "6.4.0"}
    assert unpack_call(session, 1) == ["core.version", "old-token"]
    assert unpack_call(session, 2) == ["auth.login", "msf", "top-secret"]
    assert unpack_call(session, 3) == ["core.version", "new-token"]


def test_invalid_token_is_only_retried_once():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "old-token"}),
        FakeResponse({"error": True, "error_message": "Token has expired"}),
        FakeResponse({"result": "success", "token": "new-token"}),
        FakeResponse({"error": True, "error_message": "Token has expired"}),
    )

    with pytest.raises(MetasploitRpcAuthError, match="expired"):
        client.call("core.version")

    assert len(session.calls) == 4


def test_request_timeout_is_retried_and_raised_as_typed_error():
    client, session = make_client(
        requests.Timeout("top-secret timed out"),
        requests.Timeout("top-secret timed out again"),
        retries=1,
    )

    with pytest.raises(MetasploitRpcTimeoutError) as exc_info:
        client.call("core.version")

    assert len(session.calls) == 2
    assert "top-secret" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_connection_failure_is_retried():
    client, session = make_client(
        requests.ConnectionError("refused"),
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"version": "6.4.0"}),
        retries=1,
    )

    assert client.call("core.version") == {"version": "6.4.0"}
    assert len(session.calls) == 3


def test_exhausted_connection_failure_raises_typed_error():
    client, _ = make_client(requests.ConnectionError("top-secret refused"))

    with pytest.raises(MetasploitRpcConnectionError) as exc_info:
        client.call("core.version")

    assert "top-secret" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_module_methods_map_to_rpc_calls():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse([{"fullname": "auxiliary/scanner/portscan/tcp"}]),
        FakeResponse({"name": "TCP Port Scanner"}),
        FakeResponse({"RHOSTS": {"required": True}}),
        FakeResponse({"job_id": 7, "uuid": "abc"}),
    )

    assert client.search_modules("portscan") == [
        {"fullname": "auxiliary/scanner/portscan/tcp"}
    ]
    assert client.module_info("auxiliary", "scanner/portscan/tcp") == {
        "name": "TCP Port Scanner"
    }
    assert client.module_options("auxiliary", "scanner/portscan/tcp") == {
        "RHOSTS": {"required": True}
    }
    assert client.execute_module(
        "auxiliary", "scanner/portscan/tcp", {"RHOSTS": "127.0.0.1"}
    ) == {"job_id": 7, "uuid": "abc"}

    assert unpack_call(session, 1) == ["module.search", "token", "portscan"]
    assert unpack_call(session, 2) == [
        "module.info",
        "token",
        "auxiliary",
        "scanner/portscan/tcp",
    ]
    assert unpack_call(session, 3) == [
        "module.options",
        "token",
        "auxiliary",
        "scanner/portscan/tcp",
    ]
    assert unpack_call(session, 4) == [
        "module.execute",
        "token",
        "auxiliary",
        "scanner/portscan/tcp",
        {"RHOSTS": "127.0.0.1"},
    ]


def test_module_search_supports_type_filter():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse([]),
    )

    client.search_modules("scanner", module_type="auxiliary")

    assert unpack_call(session, 1) == [
        "module.search",
        "token",
        "scanner type:auxiliary",
    ]


def test_job_methods_map_to_rpc_calls():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"7": "Exploit: test"}),
        FakeResponse({"result": "success"}),
    )

    assert client.list_jobs() == {"7": "Exploit: test"}
    assert client.stop_job("7") == {"result": "success"}
    assert unpack_call(session, 1) == ["job.list", "token"]
    assert unpack_call(session, 2) == ["job.stop", "token", "7"]


def test_session_methods_map_to_rpc_calls():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"1": {"type": "shell"}}),
        FakeResponse({"write_count": 3}),
        FakeResponse({"seq": 1, "data": "ok\n"}),
        FakeResponse({"result": "success"}),
    )

    assert client.list_sessions() == {"1": {"type": "shell"}}
    assert client.write_session("1", "id\n") == {"write_count": 3}
    assert client.read_session("1") == {"seq": 1, "data": "ok\n"}
    assert client.stop_session("1") == {"result": "success"}
    assert unpack_call(session, 1) == ["session.list", "token"]
    assert unpack_call(session, 2) == ["session.shell_write", "token", "1", "id\n"]
    assert unpack_call(session, 3) == ["session.shell_read", "token", "1"]
    assert unpack_call(session, 4) == ["session.stop", "token", "1"]


def test_meterpreter_session_methods_map_to_rpc_calls():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"write_count": 6}),
        FakeResponse({"data": "uid=0\n"}),
    )

    assert client.write_session("2", "getuid", session_type="meterpreter") == {
        "write_count": 6
    }
    assert client.read_session("2", session_type="meterpreter") == {
        "data": "uid=0\n"
    }
    assert unpack_call(session, 1) == [
        "session.meterpreter_write",
        "token",
        "2",
        "getuid",
    ]
    assert unpack_call(session, 2) == [
        "session.meterpreter_read",
        "token",
        "2",
    ]


def test_session_methods_reject_unknown_session_type():
    client, session = make_client()

    with pytest.raises(MetasploitRpcError, match="Unsupported session type"):
        client.write_session("2", "getuid", session_type="unknown")

    assert session.calls == []


def test_console_methods_map_to_rpc_calls():
    client, session = make_client(
        FakeResponse({"result": "success", "token": "token"}),
        FakeResponse({"id": "0", "prompt": "msf6 > "}),
        FakeResponse({"0": {"busy": False}}),
        FakeResponse({"data": "output", "busy": False}),
        FakeResponse({"wrote": 8}),
        FakeResponse({"result": "success"}),
    )

    assert client.create_console()["id"] == "0"
    assert client.list_consoles() == {"0": {"busy": False}}
    assert client.read_console("0") == {"data": "output", "busy": False}
    assert client.write_console("0", "version\n") == {"wrote": 8}
    assert client.destroy_console("0") == {"result": "success"}
    assert unpack_call(session, 1) == ["console.create", "token"]
    assert unpack_call(session, 2) == ["console.list", "token"]
    assert unpack_call(session, 3) == ["console.read", "token", "0"]
    assert unpack_call(session, 4) == ["console.write", "token", "0", "version\n"]
    assert unpack_call(session, 5) == ["console.destroy", "token", "0"]
