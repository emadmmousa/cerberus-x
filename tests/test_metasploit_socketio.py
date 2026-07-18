import pytest
from flask import Flask
from flask_socketio import SocketIO

from orchestrator.metasploit_socketio import register_metasploit_socketio
from tools.metasploit_rpc import MetasploitRpcError


class FakeClient:
    def __init__(self):
        self.calls = []
        self.next_console_id = 0
        self.error = None

    def _record(self, method, *args):
        self.calls.append((method, args))
        if self.error:
            raise self.error

    def create_console(self):
        self._record("create_console")
        console_id = str(self.next_console_id)
        self.next_console_id += 1
        return {
            "id": console_id,
            "prompt": "msf6 > ",
            "token": "must-not-leak",
        }

    def write_console(self, console_id, command):
        self._record("write_console", console_id, command)
        return {"wrote": len(command)}

    def read_console(self, console_id):
        self._record("read_console", console_id)
        return {
            "data": "module output\n",
            "busy": False,
            "password": "must-not-leak",
        }

    def destroy_console(self, console_id):
        self._record("destroy_console", console_id)
        return {"result": "success"}


@pytest.fixture
def console_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    socketio = SocketIO(app, async_mode="threading")
    fake = FakeClient()
    register_metasploit_socketio(socketio, lambda: fake)
    emitted = []
    socketio.emit = lambda name, data, **kwargs: emitted.append(
        {"name": name, "args": [data], **kwargs}
    )
    return app, socketio, fake, emitted


def _event(emitted, name):
    matches = [event for event in emitted if event["name"] == name]
    assert len(matches) == 1
    emitted.remove(matches[0])
    return matches[0]["args"][0]


def _create_console(client, emitted):
    client.emit("msf_console_create")
    return _event(emitted, "msf_console_created")


def test_create_emits_sanitized_console_details(console_app):
    app, socketio, fake, emitted = console_app
    client = socketio.test_client(app)

    created = _create_console(client, emitted)

    assert created == {"console": {"id": "0", "prompt": "msf6 > "}}
    assert fake.calls == [("create_console", ())]


def test_write_appends_newline_only_when_missing(console_app):
    app, socketio, fake, emitted = console_app
    client = socketio.test_client(app)
    _create_console(client, emitted)

    client.emit("msf_console_write", {"console_id": "0", "command": "version"})
    first = _event(emitted, "msf_console_written")
    client.emit("msf_console_write", {"console_id": "0", "command": "help\n"})
    second = _event(emitted, "msf_console_written")

    assert first == {"console_id": "0", "result": {"wrote": 8}}
    assert second == {"console_id": "0", "result": {"wrote": 5}}
    assert fake.calls[-2:] == [
        ("write_console", ("0", "version\n")),
        ("write_console", ("0", "help\n")),
    ]


def test_read_emits_sanitized_console_output(console_app):
    app, socketio, _, emitted = console_app
    client = socketio.test_client(app)
    _create_console(client, emitted)

    client.emit("msf_console_read", {"console_id": "0"})

    assert _event(emitted, "msf_console_output") == {
        "console_id": "0",
        "output": {"data": "module output\n", "busy": False},
    }


def test_destroy_removes_console_ownership(console_app):
    app, socketio, fake, emitted = console_app
    client = socketio.test_client(app)
    _create_console(client, emitted)

    client.emit("msf_console_destroy", {"console_id": "0"})
    assert _event(emitted, "msf_console_destroyed") == {
        "console_id": "0",
        "result": {"result": "success"},
    }

    client.emit("msf_console_read", {"console_id": "0"})
    assert _event(emitted, "msf_console_error") == {
        "event": "msf_console_read",
        "error": "Console is not owned by this connection",
        "code": "console_not_found",
    }
    assert fake.calls[-1] == ("destroy_console", ("0",))


def test_foreign_console_ids_are_inaccessible(console_app):
    app, socketio, fake, emitted = console_app
    owner = socketio.test_client(app)
    stranger = socketio.test_client(app)
    _create_console(owner, emitted)

    stranger.emit(
        "msf_console_write",
        {"console_id": "0", "command": "sessions"},
    )

    assert _event(emitted, "msf_console_error")["code"] == "console_not_found"
    assert not any(call[0] == "write_console" for call in fake.calls)


def test_disconnect_destroys_all_consoles_owned_by_sid(console_app):
    app, socketio, fake, emitted = console_app
    client = socketio.test_client(app)
    _create_console(client, emitted)
    _create_console(client, emitted)

    client.disconnect()

    assert fake.calls[-2:] == [
        ("destroy_console", ("0",)),
        ("destroy_console", ("1",)),
    ]


def test_rpc_errors_are_structured_and_redacted(
    console_app, monkeypatch
):
    app, socketio, fake, emitted = console_app
    client = socketio.test_client(app)
    monkeypatch.setenv("MSF_RPC_PASSWORD", "rpc-secret")
    fake.error = MetasploitRpcError("login failed for rpc-secret")

    client.emit("msf_console_create")

    assert _event(emitted, "msf_console_error") == {
        "event": "msf_console_create",
        "error": "login failed for [REDACTED]",
        "code": "metasploit_unavailable",
    }


def test_invalid_payload_emits_structured_error(console_app):
    app, socketio, _, emitted = console_app
    client = socketio.test_client(app)

    client.emit("msf_console_write", {"command": "version"})

    assert _event(emitted, "msf_console_error") == {
        "event": "msf_console_write",
        "error": "A console_id is required",
        "code": "invalid_input",
    }
