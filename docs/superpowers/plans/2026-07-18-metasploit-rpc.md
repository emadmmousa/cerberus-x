# Metasploit RPC Interactive Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a localhost-only, full Metasploit RPC integration with module execution, jobs, sessions, and an interactive console.

**Architecture:** A dedicated Metasploit container owns all RPC state and persists workspace data in PostgreSQL. A small MessagePack RPC client is shared by Flask routes and Celery tasks; Socket.IO provides browser console I/O while keeping credentials server-side.

**Tech Stack:** Python 3.12, Flask, Flask-SocketIO, Celery, MessagePack, Docker Compose, Metasploit Framework, PostgreSQL, pytest.

## Global Constraints

- Dashboard/API host binding is exactly `127.0.0.1:5000`.
- Metasploit RPC and PostgreSQL ports are not published to the host.
- RPC credentials come only from environment variables.
- Browser responses and logs never contain the RPC password or authentication token.
- Existing scanner workflows remain compatible.
- Module execution is explicit; no automatic exploit or payload selection is introduced.

---

### Task 1: RPC configuration and client

**Files:**
- Create: `src/tools/metasploit_rpc.py`
- Create: `tests/test_metasploit_rpc.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `MetasploitRpcConfig.from_env()`
- Produces: `MetasploitRpcClient.call(method, *args)`
- Produces module, job, session, and console methods used by later tasks.

- [ ] Write tests using a fake `requests.Session` for login, token attachment and one-shot reauthentication, byte-key normalization, sanitized RPC errors, SSL verification, request timeout, module execution, shell/meterpreter sessions, jobs, and consoles.
- [ ] Run `pytest tests/test_metasploit_rpc.py -v`; expect failures because the client does not exist.
- [ ] Add `msgpack` and implement the client with Metasploit's exact `binary/message-pack` content type, `MSF_RPC_VERIFY_SSL` defaulting to false for local self-signed `msfrpcd`, bounded retries, timeout, JSON-safe normalization, sanitized server error details, and typed client exceptions.
- [ ] Run `pytest tests/test_metasploit_rpc.py -v`; expect all tests to pass.

### Task 2: RPC-backed Metasploit wrapper and Celery task

**Files:**
- Modify: `src/tools/wrappers/metasploit.py`
- Modify: `src/orchestrator/tasks.py`
- Create: `tests/test_metasploit_wrapper.py`

**Interfaces:**
- Consumes: `MetasploitRpcClient`.
- Produces: `scan(target: str, args: list[str] | None) -> dict`.

- [ ] Test parsing `module`, `KEY=VALUE` options, URL-to-host conversion, explicit `RHOSTS`, malformed arguments, and structured execution results.
- [ ] Run `pytest tests/test_metasploit_wrapper.py -v`; expect failures against the subprocess wrapper.
- [ ] Replace resource-file/subprocess execution with RPC module option validation and execution.
- [ ] Keep the Celery signature stable and return structured errors instead of leaking credentials/tokens.
- [ ] Run wrapper tests and a focused task serialization check.

### Task 3: Compose Metasploit runtime

**Files:**
- Create: `docker/metasploit.Dockerfile`
- Create: `docker/metasploit-entrypoint.sh`
- Modify: `docker-compose.yml`
- Modify: `docker/docker-compose.yml`
- Create: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces internal `metasploit:55553` RPC endpoint.
- Produces PostgreSQL-backed persistent Metasploit workspace.

- [ ] Add `postgres` with a health check and named data volume.
- [ ] Build a multi-architecture Metasploit image from a supported base, initialize `database.yml`, wait for PostgreSQL, run `msfdb init`, and start `msfrpcd` with environment credentials.
- [ ] Add an RPC health check without publishing port `55553`.
- [ ] Pass RPC environment variables to orchestrator and workers.
- [ ] Bind dashboard port as `127.0.0.1:5000:5000`.
- [ ] Document non-secret defaults and required password generation in `.env.example`; ignore `.env`.
- [ ] Run `docker compose config`; expect valid configuration with no RPC/PostgreSQL host ports.

### Task 4: Metasploit HTTP API

**Files:**
- Create: `src/orchestrator/metasploit_api.py`
- Modify: `src/orchestrator/dashboard.py`
- Create: `tests/test_metasploit_api.py`

**Interfaces:**
- Consumes: a client factory returning `MetasploitRpcClient`.
- Produces the `/api/metasploit/*` routes from the design.

- [ ] Write Flask client tests for health, module search/detail/run, jobs, sessions, validation errors, not-found errors, and unavailable RPC responses.
- [ ] Run `pytest tests/test_metasploit_api.py -v`; expect missing blueprint failures.
- [ ] Implement a Flask blueprint with centralized error mapping and strict request validation.
- [ ] Register the blueprint in `dashboard.py`.
- [ ] Run the API tests; expect all to pass.

### Task 5: Socket.IO interactive console

**Files:**
- Create: `src/orchestrator/metasploit_socketio.py`
- Modify: `src/orchestrator/dashboard.py`
- Create: `tests/test_metasploit_socketio.py`

**Interfaces:**
- Produces handlers for `msf_console_create`, `msf_console_write`, `msf_console_read`, and `msf_console_destroy`.

- [ ] Test console ownership per Socket.IO SID, command newline handling, output events, explicit destruction, disconnect cleanup, and inaccessible foreign console IDs.
- [ ] Run the focused test; expect missing-handler failures.
- [ ] Implement the registry with a lock, client factory injection, and cleanup on disconnect.
- [ ] Register handlers once during dashboard setup.
- [ ] Run the Socket.IO tests; expect all to pass.

### Task 6: Dashboard controls

**Files:**
- Modify: `src/orchestrator/templates/index.html`
- Create: `tests/test_dashboard.py`

**Interfaces:**
- Consumes the HTTP and Socket.IO APIs from Tasks 4 and 5.

- [ ] Add a render smoke test asserting Metasploit module, jobs, sessions, and console controls.
- [ ] Add module search/run controls, jobs/session refresh controls, session command controls, and a text-only terminal.
- [ ] Ensure dynamic values are inserted with `textContent`, not `innerHTML`.
- [ ] Poll the console only while open and destroy it on close/unload.
- [ ] Run dashboard and API tests.

### Task 7: Playbook and end-to-end verification

**Files:**
- Modify: `playbooks/default.yaml`
- Modify: `README.md`

**Interfaces:**
- Consumes all prior tasks.

- [ ] Add a non-destructive Metasploit auxiliary scanner example to the vulnerability phase.
- [ ] Document `.env` creation, startup, health check, API usage, playbook format, jobs/sessions, and console use.
- [ ] Run `pytest -v`; expect all tests to pass.
- [ ] Run `docker compose build`; expect all images to build.
- [ ] Run `docker compose up -d`; expect all services healthy.
- [ ] Verify `docker compose exec orchestrator` can authenticate and call `core.version`.
- [ ] Verify `docker compose ps` exposes only `127.0.0.1:5000` plus the existing Redis mapping; confirm no Metasploit/PostgreSQL host mapping.
- [ ] Run a safe auxiliary module against an explicitly authorized local/test target and verify a structured job result.
