import pytest
from flask import Flask

from orchestrator.metasploit_api import create_metasploit_blueprint
from tools.metasploit_rpc import (
    MetasploitRpcAuthError,
    MetasploitRpcConnectionError,
    MetasploitRpcError,
)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.modules = [{"fullname": "auxiliary/scanner/http/title"}]
        self.info = {"name": "HTTP title", "type": "auxiliary"}
        self.options = {
            "RHOSTS": {"required": True},
            "RPORT": {"required": False, "default": 80},
        }
        self.execution = {"job_id": 7, "uuid": "run-abc"}
        self.jobs = {"7": {"name": "scanner/http/title"}}
        self.sessions = {
            "2": {"type": "shell", "session_host": "192.0.2.10"},
            "3": {"type": "meterpreter", "session_host": "192.0.2.11"},
        }
        self.error = None

    def _record(self, method, *args):
        self.calls.append((method, args))
        if self.error:
            raise self.error

    def call(self, method, *args):
        self._record("call", method, *args)
        return {"version": "6.4.0", "token": "must-not-leak"}

    def search_modules(self, query, *, module_type=None):
        self._record("search_modules", query, module_type)
        return self.modules

    def module_info(self, module_type, module_name):
        self._record("module_info", module_type, module_name)
        return self.info

    def module_options(self, module_type, module_name):
        self._record("module_options", module_type, module_name)
        return self.options

    def execute_module(self, module_type, module_name, options):
        self._record("execute_module", module_type, module_name, options)
        return self.execution

    def list_jobs(self):
        self._record("list_jobs")
        return self.jobs

    def stop_job(self, job_id):
        self._record("stop_job", job_id)
        return {"result": "success"}

    def list_sessions(self):
        self._record("list_sessions")
        return self.sessions

    def write_session(self, session_id, command, *, session_type="shell"):
        self._record("write_session", session_id, command, session_type)
        return {"write_count": len(command)}

    def stop_session(self, session_id):
        self._record("stop_session", session_id)
        return {"result": "success"}


@pytest.fixture
def api():
    fake = FakeClient()
    app = Flask(__name__)
    app.register_blueprint(create_metasploit_blueprint(lambda: fake))
    return app.test_client(), fake


def test_health_reports_rpc_version_without_secrets(api):
    client, fake = api

    response = client.get("/api/metasploit/health")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "rpc": {"version": "6.4.0"},
    }
    assert fake.calls == [("call", ("core.version",))]


def test_module_search_passes_query_and_type(api):
    client, fake = api

    response = client.get(
        "/api/metasploit/modules?q=http%20title&type=auxiliary"
    )

    assert response.status_code == 200
    assert response.get_json() == {"modules": fake.modules}
    assert fake.calls == [
        ("search_modules", ("http title", "auxiliary"))
    ]


def test_module_detail_returns_info_and_options(api):
    client, fake = api

    response = client.get(
        "/api/metasploit/modules/auxiliary/scanner/http/title"
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "module": fake.info,
        "options": fake.options,
    }
    assert fake.calls == [
        ("module_info", ("auxiliary", "scanner/http/title")),
        ("module_options", ("auxiliary", "scanner/http/title")),
    ]


def test_module_run_validates_options_then_executes(api):
    client, fake = api

    response = client.post(
        "/api/metasploit/modules/run",
        json={
            "type": "auxiliary",
            "name": "scanner/http/title",
            "options": {"RHOSTS": "192.0.2.10"},
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "module": "auxiliary/scanner/http/title",
        "result": fake.execution,
    }
    assert fake.calls == [
        ("module_options", ("auxiliary", "scanner/http/title")),
        (
            "execute_module",
            (
                "auxiliary",
                "scanner/http/title",
                {"RHOSTS": "192.0.2.10"},
            ),
        ),
    ]


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (None, "invalid_json"),
        ({}, "invalid_input"),
        (
            {
                "type": "unknown",
                "name": "scanner/http/title",
                "options": {},
            },
            "invalid_module_type",
        ),
        (
            {
                "type": "auxiliary",
                "name": "../scanner/http/title",
                "options": {},
            },
            "invalid_input",
        ),
        (
            {
                "type": "auxiliary",
                "name": "scanner/http/title",
                "options": [],
            },
            "invalid_options",
        ),
    ],
)
def test_module_run_rejects_invalid_input(api, payload, code):
    client, fake = api

    response = client.post("/api/metasploit/modules/run", json=payload)

    assert response.status_code == 400
    assert response.get_json()["code"] == code
    assert fake.calls == []


def test_module_run_rejects_missing_required_options(api):
    client, fake = api

    response = client.post(
        "/api/metasploit/modules/run",
        json={
            "type": "auxiliary",
            "name": "scanner/http/title",
            "options": {},
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Missing required module options: RHOSTS",
        "code": "missing_required_options",
    }
    assert not any(call[0] == "execute_module" for call in fake.calls)


def test_jobs_can_be_listed_and_stopped(api):
    client, fake = api

    listed = client.get("/api/metasploit/jobs")
    stopped = client.delete("/api/metasploit/jobs/7")

    assert listed.get_json() == {"jobs": fake.jobs}
    assert stopped.get_json() == {
        "job_id": "7",
        "result": {"result": "success"},
    }
    assert ("stop_job", ("7",)) in fake.calls


def test_missing_job_returns_not_found(api):
    client, fake = api

    response = client.delete("/api/metasploit/jobs/999")

    assert response.status_code == 404
    assert response.get_json() == {
        "error": "Metasploit job 999 was not found",
        "code": "job_not_found",
    }
    assert not any(call[0] == "stop_job" for call in fake.calls)


def test_sessions_can_be_listed_commanded_and_closed(api):
    client, fake = api

    listed = client.get("/api/metasploit/sessions")
    shell_commanded = client.post(
        "/api/metasploit/sessions/2/command",
        json={"command": "id"},
    )
    meterpreter_commanded = client.post(
        "/api/metasploit/sessions/3/command",
        json={"command": "sysinfo"},
    )
    closed = client.delete("/api/metasploit/sessions/2")

    assert listed.get_json() == {"sessions": fake.sessions}
    assert shell_commanded.get_json() == {
        "session_id": "2",
        "result": {"write_count": 3},
    }
    assert meterpreter_commanded.get_json() == {
        "session_id": "3",
        "result": {"write_count": 7},
    }
    assert closed.get_json() == {
        "session_id": "2",
        "result": {"result": "success"},
    }
    assert ("write_session", ("2", "id\n", "shell")) in fake.calls
    assert ("write_session", ("3", "sysinfo", "meterpreter")) in fake.calls
    assert ("stop_session", ("2",)) in fake.calls


def test_module_detail_scrubs_sensitive_option_keys(api):
    client, fake = api
    fake.options = {
        "RHOSTS": {"required": True},
        "SMBPass": {"required": False, "default": "secret"},
        "USERPASS": {"required": False},
        "AuthToken": {"required": False, "default": "tok"},
    }

    response = client.get(
        "/api/metasploit/modules/auxiliary/scanner/http/title"
    )

    assert response.status_code == 200
    assert response.get_json()["options"] == {
        "RHOSTS": {"required": True},
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/metasploit/sessions/999/command", {"command": "id"}),
        ("delete", "/api/metasploit/sessions/999", None),
    ],
)
def test_missing_session_returns_not_found(api, method, path, payload):
    client, _ = api

    response = getattr(client, method)(path, json=payload)

    assert response.status_code == 404
    assert response.get_json()["code"] == "session_not_found"


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"command": ""}, {"command": 123}],
)
def test_session_command_requires_nonempty_string(api, payload):
    client, fake = api

    response = client.post(
        "/api/metasploit/sessions/2/command", json=payload
    )

    assert response.status_code == 400
    assert response.get_json()["code"] in {"invalid_json", "invalid_input"}
    assert fake.calls == []


@pytest.mark.parametrize(
    "error",
    [
        MetasploitRpcConnectionError("RPC unavailable"),
        MetasploitRpcAuthError("Authentication failed"),
        MetasploitRpcError("RPC call failed"),
    ],
)
def test_rpc_failures_return_service_unavailable(api, error):
    client, fake = api
    fake.error = error

    response = client.get("/api/metasploit/jobs")

    assert response.status_code == 503
    assert response.get_json() == {
        "error": str(error),
        "code": "metasploit_unavailable",
    }


def test_dashboard_registers_metasploit_blueprint():
    from orchestrator.dashboard import app

    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/api/metasploit/health" in rules
    assert "/api/metasploit/modules/run" in rules
    assert "/api/metasploit/sessions/<session_id>/command" in rules

