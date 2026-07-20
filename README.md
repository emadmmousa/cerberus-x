# Cerberus-X

Universal Offensive Orchestration Framework integrating security scanners and Metasploit RPC into a single operator workflow.

## Status

Active development. Core wrappers, Celery playbooks, dashboard, and Metasploit MessagePack RPC are available.

## Architecture

- **Orchestrator** (Flask + Socket.IO) — localhost dashboard/API and playbook submission
- **Workers** (Celery + Redis) — run scanner and Metasploit module tasks
- **Metasploit** — DB-connected `msfconsole` with MessagePack `msgrpc` on the internal Docker network
- **PostgreSQL** — persistent Metasploit workspace (internal only)
- **Tool Wrappers** — standardized scanner/RPC interfaces

The dashboard is published only as `127.0.0.1:5000`. Metasploit RPC (`55553`) and PostgreSQL (`5432`) are never published to the host.

## Quick Start

```bash
cp .env.example .env
# Fill POSTGRES_PASSWORD and MSF_RPC_PASSWORD with strong secrets:
# openssl rand -hex 24

docker compose up -d

# Health
curl -s http://127.0.0.1:5000/api/metasploit/health

# Playbook
docker compose exec orchestrator \
  python -m orchestrator.cli \
  --target https://example.com \
  --playbook playbooks/default.yaml
```

Open the dashboard at [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Metasploit RPC

Credentials come from `.env`:

- `MSF_RPC_USER` / `MSF_RPC_PASSWORD`
- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`

API routes:

- `GET /api/metasploit/health`
- `GET /api/metasploit/modules?q=...&type=...`
- `GET /api/metasploit/modules/<type>/<path>`
- `POST /api/metasploit/modules/run`
- `GET|DELETE /api/metasploit/jobs[/<id>]`
- `GET|DELETE /api/metasploit/sessions[/<id>]`
- `POST /api/metasploit/sessions/<id>/command`

Socket.IO console events:

- `msf_console_create` / `msf_console_write` / `msf_console_read` / `msf_console_destroy`

Playbook Metasploit args:

```yaml
- tool: metasploit
  args:
    - auxiliary/scanner/portscan/tcp
    - RPORTS=80,443
    - THREADS=10
```

`RHOSTS` is derived from the CLI/API target unless provided explicitly.

## MCP + AI Mode

Cerberus-X exposes a Model Context Protocol façade on the orchestrator:

- `POST /mcp` — JSON-RPC (`initialize`, `tools/list`, `tools/call`)
- `GET /mcp/sse` — SSE heartbeat stream
- Auth: `Authorization: Bearer <CERBERUS_MCP_API_KEY>` or `X-API-Key`
- Tools: `session_create`, `list_tools`, `run_tool`, `get_job_status`, `get_findings`, `list_sessions`, `suggest_next_phase`

Configure in `.env` (see `.env.example`):

```bash
CERBERUS_MCP_API_KEY=<random>          # python -c "import secrets; print(secrets.token_urlsafe(32))"
CERBERUS_LLM_BASE_URL=http://ollama:11434/v1   # recommended with compose `ollama` service
CERBERUS_LLM_MODEL=llama3.2
```

`docker compose up -d` starts **Ollama** and pulls `llama3.2` via `ollama-pull`. If the LLM is down, AI Mode falls back to the heuristic planner.

Mission Control **AI Mode** posts `ai_mode: true` to `/api/run`. High-risk tools require confirm when `CERBERUS_AI_REQUIRE_CONFIRM=true`.

Design/plan docs:

- `docs/superpowers/specs/2026-07-20-ai-mcp-orchestration-design.md`
- `docs/superpowers/plans/2026-07-20-ai-mcp-orchestration.md`

## Development

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace \
  -e PYTHONPATH=/workspace:/workspace/src \
  cerberus-x-orchestrator \
  sh -c 'pip install -q -r requirements.txt && pytest -q'
```

## Notes

- Only run modules/sessions against systems you are authorized to test.
- The browser never receives RPC passwords or authentication tokens.
- Prefer non-destructive auxiliary modules in the default playbook.
