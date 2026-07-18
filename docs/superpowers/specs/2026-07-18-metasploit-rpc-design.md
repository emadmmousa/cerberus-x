# Metasploit RPC Interactive Orchestration Design

## Goal

Add a dedicated Metasploit RPC service to Cerberus-X that supports structured module execution, job and session management, and an interactive RPC console through the localhost-only dashboard.

## Architecture

The Compose stack adds a dedicated `metasploit` service and PostgreSQL database. Metasploit runs a DB-connected `msfconsole` that loads MessagePack `msgrpc` on the internal Compose network; its port is not published to the host. The orchestrator and Celery workers authenticate using credentials supplied through environment variables.

The dashboard remains the only host-facing entry point and binds to `127.0.0.1:5000`. Browser code never receives the RPC password.

Data flows:

- Browser → Flask/Socket.IO → Metasploit RPC for modules, jobs, sessions, and consoles.
- Playbook/CLI → Celery worker → Metasploit RPC for background module execution.
- Metasploit → PostgreSQL for persistent workspace state.

## Backend Components

### RPC client

Create a focused `MetasploitRpcClient` responsible for:

- RPC authentication with one-shot reauthentication for invalid or expired tokens, bounded retries, and request timeouts.
- Module search, metadata, option lookup, validation, and execution.
- Job listing and stopping.
- Shell and Meterpreter session listing, type-aware read/write, command execution, and closing.
- Console creation, read, write, and destruction.
- Normalizing byte-keyed MessagePack responses into JSON-safe Python values.

Requests use Metasploit's exact `binary/message-pack` content type. The client reads `MSF_RPC_HOST`, `MSF_RPC_PORT`, `MSF_RPC_USER`, `MSF_RPC_PASSWORD`, `MSF_RPC_SSL`, and `MSF_RPC_VERIFY_SSL`. Certificate verification defaults to false for the local self-signed `msfrpcd` endpoint and can be enabled for deployments with trusted certificates. Sanitized RPC `error_message` details remain available to callers, while passwords and authentication tokens never appear in exceptions, API responses, or logs.

### Wrapper and Celery

Replace the current `msfconsole` subprocess wrapper with the RPC client. A playbook Metasploit entry accepts:

```yaml
- tool: metasploit
  args:
    - auxiliary/scanner/portscan/tcp
    - RPORTS=1-1024
    - THREADS=10
```

The first argument is the module path; remaining `KEY=VALUE` arguments become module options. `RHOSTS` is derived from the target unless explicitly supplied. Celery returns a structured result containing the module, job identifier, UUID, and normalized RPC response.

### HTTP and Socket.IO API

Add localhost-only routes:

- `GET /api/metasploit/health`
- `GET /api/metasploit/modules?q=...&type=...`
- `GET /api/metasploit/modules/<type>/<path>`
- `POST /api/metasploit/modules/run`
- `GET /api/metasploit/jobs`
- `DELETE /api/metasploit/jobs/<id>`
- `GET /api/metasploit/sessions`
- `POST /api/metasploit/sessions/<id>/command`
- `DELETE /api/metasploit/sessions/<id>`

Socket.IO events manage interactive consoles:

- `msf_console_create`
- `msf_console_write`
- `msf_console_read`
- `msf_console_destroy`

Console ownership is tracked per Socket.IO connection. Disconnecting destroys consoles owned by that browser connection.

## Frontend

Extend the existing dashboard without introducing a frontend framework:

- Module search and runner with module type/path, target, and options JSON.
- Jobs panel with refresh and stop actions.
- Sessions panel with refresh, command input, and close actions.
- Interactive terminal panel that creates one RPC console, sends commands, polls output only while open, and destroys it on close/unload.
- Existing scan controls and result display remain available.

All dynamic output uses text rendering rather than HTML interpolation.

## Error Handling and Safety

- RPC connection and authentication failures return `503`.
- Invalid input, unknown module types, malformed options, and missing required module options return `400`.
- Unknown jobs, sessions, or consoles return `404`.
- RPC and console operations have bounded timeouts.
- API errors use `{ "error": "...", "code": "..." }`.
- The dashboard binds only to localhost.
- Metasploit RPC and PostgreSQL are internal-only services.
- `.env.example` documents generated credential variables; `.env` remains ignored.
- Module execution requires explicit user input. No automatic exploit selection or payload generation is added.

## Testing

- Unit tests mock HTTP/MessagePack transport and cover authentication, normalization, module execution, jobs, sessions, consoles, and failures.
- Wrapper tests cover target hostname conversion and playbook argument parsing.
- Dashboard tests mock the client and verify status codes and response shapes.
- Compose smoke checks verify PostgreSQL and Metasploit health, RPC authentication from the orchestrator, localhost binding, and no host-published RPC/database ports.

## Success Criteria

- `docker compose up -d` starts healthy Redis, PostgreSQL, Metasploit, orchestrator, and workers.
- The orchestrator authenticates to Metasploit RPC without exposing credentials.
- Users can search and run modules, inspect/stop jobs, operate/close sessions, and use an interactive RPC console.
- Playbook Metasploit tasks execute over RPC and return structured results.
- Automated tests pass and existing scanners continue to operate.
