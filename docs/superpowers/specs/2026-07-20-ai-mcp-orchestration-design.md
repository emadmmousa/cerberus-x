# AI Orchestration (MCP Phase 1) Design

## Goal

Expose Cerberus-X capabilities through a Model Context Protocol (MCP) server so external agents (and a future in-cluster LLM) can discover tools, run scans, and read findings — without replacing the existing YAML playbook + DecisionEngine path.

Phase 1 delivers the **MCP foundation only**. Local/cloud LLM planning, RAG memory, and full “AI Mode” missions are Phase 2+.

## Decisions (approved)

| Topic | Choice |
| --- | --- |
| Delivery order | MCP first; LLM as MCP client in Phase 2 |
| MCP host | Inside Flask orchestrator now; extract to `ai-orchestrator` service later |
| Transport | Streamable HTTP / SSE at `/mcp` |
| Safety (Phase 1) | All `_TASK_MAP` tools allowed; every call logged + rate-limited; human confirm for exploits deferred to later phase |
| Auth | Shared API key **and** per-session `session_id` |
| Playbooks | Unchanged default path; MCP is additive |
| UI | Optional MCP activity strip deferred unless needed for debugging; no AI Mode toggle in Phase 1 |

## Current state (baseline)

- Missions: `POST /api/run` → Flask thread → Celery `group`/`chain` via `_TASK_MAP` in `src/orchestrator/tasks.py`
- Decisioning: rule-based `DecisionEngine` + `playbooks/default.yaml`
- Results: SQLite (`database.py`); job status largely in-memory `playbook_jobs`
- Realtime: Socket.IO for logs / MSF console; mission UI polls HTTP
- No LLM, MCP, or OpenAI-compatible client in product code today

## Architecture

```text
External MCP client (Cursor / Claude / future AI service)
        │  Bearer / X-API-Key
        ▼
 Flask orchestrator
   ├── /mcp  (SSE / Streamable HTTP MCP)
   │     tools: session_create, list_tools, run_tool,
   │            get_job_status, get_findings, list_sessions
   ├── existing /api/* (playbooks, results, proxy)
   └── Redis
         ├── Celery broker/backend
         └── MCP sessions + audit + rate limits
        │
        ▼
 Celery workers → tool wrappers (unchanged)
        │
        ▼
 SQLite results (existing schema)
```

**Approach:** Thin MCP façade on Flask. Tools wrap existing Celery tasks and result APIs. DecisionEngine and YAML playbooks remain the fallback and default UI path.

### Components (Phase 1)

| Component | Responsibility |
| --- | --- |
| MCP HTTP/SSE endpoint | Protocol transport at `/mcp` |
| Tool adapters | Map MCP tool calls → `_TASK_MAP` / DB queries |
| Session manager | Create/validate `session_id` in Redis |
| Audit / rate limiter | Append-only action log; per-session rate limits |
| Auth middleware | Require `CERBERUS_MCP_API_KEY` on MCP routes |

### Non-goals (Phase 1)

- No in-cluster LLM (Ollama/vLLM/cloud)
- No RAG / vector memory
- No dynamic playbook generation
- No replacement of DecisionEngine
- No operator confirmation gate for high-risk tools (logged only)
- No full Mission Control “AI Mode” toggle

## MCP tools

### `session_create`

**Args:** `target` (string), optional `label`  
**Returns:** `{ session_id, target, created_at }`  
Creates a Redis session used for audit and rate limiting.

### `list_tools`

**Args:** none (or optional `category`)  
**Returns:** list of `{ name, description, risk, parameters_schema }` derived from `_TASK_MAP` (+ short static metadata map).  
Does not invent tools outside the registry.

### `run_tool`

**Args:** `session_id`, `tool`, `target`, optional `args` (list/string map), optional `use_proxy`, `proxy_protocol`, `evasion`  
**Returns:** `{ task_id, tool, target, accepted_at }`  
Enqueues the matching Celery task. Validates `tool ∈ _TASK_MAP`. Rejects unknown tools (prevents hallucination of names).

### `get_job_status`

**Args:** `session_id`, `task_id`  
**Returns:** Celery/AsyncResult-style status (`PENDING` / `STARTED` / `SUCCESS` / `FAILURE`) plus error summary if failed.

### `get_findings`

**Args:** `session_id`, `target`, optional `job_id`, optional `tool`, optional `phase`  
**Returns:** structured rows from existing SQLite results API shape (compatible with Mission Control).

### `list_sessions`

**Args:** optional `limit`  
**Returns:** recent sessions + last N audit events (for operators / debugging).

## Auth, sessions, rate limits

- Env: `CERBERUS_MCP_API_KEY` (required when MCP enabled; MCP routes return 401 if missing/mismatch).
- Header: `Authorization: Bearer <key>` or `X-API-Key: <key>`.
- Every tool call (except possibly `session_create` itself) requires a valid `session_id`.
- Redis keys (illustrative):
  - `cerberus:mcp:session:<id>` → `{ target, created_at, label }`
  - `cerberus:mcp:audit:<id>` → list of `{ ts, tool, args_digest, task_id, status }`
  - `cerberus:mcp:ratelimit:<id>` → sliding window counter
- Default rate limit: configurable (e.g. 30 `run_tool` / minute / session); exceeded → MCP error, no enqueue.
- All MCP actions also emit a Socket.IO `log` line (or dedicated `mcp_action` event) for Live Event Stream visibility.

## Safety model (Phase 1)

- Allow any registered tool, including exploit/cred tools.
- Mitigations: API key, session binding, rate limits, audit log, orchestrator bind defaults (`127.0.0.1` in compose).
- Phase 5 (later): explicit confirm for high-risk tools (`metasploit`, `hydra`, `sqlmap`, etc.).

## Validation against hallucination

Before enqueue:

1. `tool` must exist in `_TASK_MAP`
2. `args` must be a list of strings (or coerced); reject nested executable blobs
3. `target` required non-empty string
4. Optional allowlist of known CLI flags per tool can land in Phase 1.1 if needed; not blocking for MVP

Malformed AI/agent output → MCP tool error; orchestrator never runs arbitrary shell.

## Integration with existing APIs

| Existing | MCP use |
| --- | --- |
| `_TASK_MAP` / `run_*_task` | `run_tool` |
| Celery result backend | `get_job_status` |
| `database.get_results` / `/results` | `get_findings` |
| `playbook_jobs` | Not required for single-tool MCP runs; optional later for AI-driven multi-phase jobs |
| DecisionEngine | Unchanged; unused by Phase 1 MCP path |

Single-tool MCP runs are first-class. Multi-phase “AI missions” wait until Phase 2 (LLM proposes phases; executor still uses these MCP tools or an internal equivalent).

## Configuration

| Variable | Purpose |
| --- | --- |
| `CERBERUS_MCP_ENABLED` | Feature flag (default `true` in dev, explicit in prod) |
| `CERBERUS_MCP_API_KEY` | Shared secret |
| `CERBERUS_MCP_RATE_LIMIT_PER_MIN` | Per-session `run_tool` cap |
| Redis URL | Existing Celery/broker settings |

Document Cursor MCP client snippet in README (URL + header).

## Testing

- Unit: session create/validate; rate limit; unknown tool rejected; auth failure
- Integration: MCP `run_tool` → mocked Celery task accepted; `get_findings` reads fixture DB rows
- No live target scans required in CI

## Rollout

1. Implement MCP module + wire into Flask app
2. Redis session/audit helpers
3. Tests + `.env.example` keys
4. README: connect Cursor/Claude to `/mcp`
5. Branch: `feature/ai-orchestration` (or land on `main` behind `CERBERUS_MCP_ENABLED`)

## Phase 2 preview (out of scope, reserved)

- Separate AI service as MCP client
- Mission Control “AI Mode” toggle
- Local LLM (Ollama/Mistral) + cloud fallback
- `suggest_next_phase` / plan JSON → validated phase executor
- DecisionEngine timeout fallback
- RAG over past mission embeddings

## Success criteria (Phase 1)

- External MCP client can list tools and run at least one recon tool end-to-end against a lab target
- Every call is attributable to `session_id` in Redis audit
- Unknown tool names never reach workers
- Default playbook missions still work unchanged with MCP disabled or unused

## Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| Agent invents tools/args | Registry validation; typed args |
| Open exploit surface via MCP | API key + localhost default + rate limit + audit; confirm gates later |
| Orchestrator bloat | Keep MCP in isolated package (`orchestrator/mcp_*`); extract service in Phase 2 |
| In-memory job map confusion | Prefer Celery `task_id` for MCP status, not `playbook_jobs` |
