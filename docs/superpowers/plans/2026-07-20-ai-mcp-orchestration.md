# AI MCP Orchestration — Full Implementation Plan (Phases 1–5)

## Status (2026-07-20)

**Shipped** (Phases 1–5). Confirm gate defaults **off**. Unrestricted Ollama persona:
`docker/ollama/Modelfile` → `cerberus-x`. See [`docs/user_manual.md`](../../user_manual.md).

> **For agentic workers:** Execute tasks in order. Prefer inline execution for this plan (user requested implement-all-at-once).

**Goal:** Ship adaptive AI orchestration on Cerberus-X: MCP tool surface, LLM/heuristic planner, mission memory, NL mission entry, and operator safety/UI — while keeping YAML playbooks + DecisionEngine as fallback.

**Architecture:** MCP façade on Flask (`/mcp`) wraps `_TASK_MAP` + Redis sessions. AI planner (OpenAI-compatible LLM with deterministic heuristic fallback) proposes phases; executor validates tools then enqueues Celery. Lightweight local memory (SQLite embeddings via hashing) stores successful strategies. Mission Control gains AI Mode, confirm-for-risk, and MCP/AI activity.

**Tech Stack:** Flask, Redis, Celery, existing wrappers, `requests` for OpenAI-compatible APIs, React SPA, pytest.

## Global Constraints

- Never execute a tool name outside `_TASK_MAP`.
- MCP requires `CERBERUS_MCP_API_KEY` + `session_id` (except `session_create`).
- High-risk tools require `confirm=true` when `CERBERUS_AI_REQUIRE_CONFIRM=true` (**default false** as of 2026-07-20 unrestricted orchestration).
- If LLM unavailable/malformed → DecisionEngine / heuristic planner fallback.
- No credentials or `.env` secrets in prompts sent to cloud LLMs (sanitize).
- Preserve existing `/api/run` playbook behavior when `ai_mode` is false/absent.

## File map

| Path | Role |
| --- | --- |
| `src/orchestrator/mcp/auth.py` | API key check |
| `src/orchestrator/mcp/sessions.py` | Redis session + audit + rate limit |
| `src/orchestrator/mcp/registry.py` | Tool metadata over `_TASK_MAP` |
| `src/orchestrator/mcp/actions.py` | run_tool / status / findings |
| `src/orchestrator/mcp/blueprint.py` | Flask `/mcp` JSON-RPC + SSE |
| `src/orchestrator/ai/llm.py` | OpenAI-compatible chat client |
| `src/orchestrator/ai/planner.py` | suggest_next_phase + NL → plan |
| `src/orchestrator/ai/memory.py` | Store/retrieve strategy snippets |
| `src/orchestrator/ai/safety.py` | Risk classes + confirm gate |
| `src/orchestrator/ai/runner.py` | AI mission loop |
| `src/orchestrator/dashboard.py` | Wire MCP + AI Mode APIs |
| `frontend/.../MissionControl.tsx` | AI Mode + confirm UX |
| `tests/test_mcp_*.py`, `tests/test_ai_*.py` | Coverage |

---

### Task 1: MCP sessions + auth

**Files:**
- Create: `src/orchestrator/mcp/__init__.py`
- Create: `src/orchestrator/mcp/auth.py`
- Create: `src/orchestrator/mcp/sessions.py`
- Test: `tests/test_mcp_sessions.py`

**Produces:** `require_api_key(request) -> None|Response`, `create_session(target, label=None) -> dict`, `get_session(id) -> dict|None`, `audit(session_id, event)`, `check_rate_limit(session_id) -> bool`

- [ ] Implement Redis-backed sessions (fakeredis or mock in tests)
- [ ] Rate limit `run_tool` via env `CERBERUS_MCP_RATE_LIMIT_PER_MIN` (default 30)
- [ ] Commit

### Task 2: MCP registry + actions

**Files:**
- Create: `src/orchestrator/mcp/registry.py`
- Create: `src/orchestrator/mcp/actions.py`
- Test: `tests/test_mcp_actions.py`

**Produces:** `list_tool_descriptors()`, `enqueue_tool(...)`, `task_status(task_id)`, `findings(...)`

- [ ] Map `_TASK_MAP` keys to descriptors with `risk: low|high`
- [ ] Reject unknown tools
- [ ] Commit

### Task 3: MCP Flask blueprint

**Files:**
- Create: `src/orchestrator/mcp/blueprint.py`
- Modify: `src/orchestrator/dashboard.py`
- Modify: `.env.example`
- Test: `tests/test_mcp_http.py`

- [ ] `POST /mcp` JSON-RPC: `tools/list`, `tools/call`
- [ ] `GET /mcp/sse` heartbeat stream (optional stub OK)
- [ ] Tools: session_create, list_tools, run_tool, get_job_status, get_findings, list_sessions
- [ ] Commit

### Task 4: AI safety + LLM client + heuristic planner

**Files:**
- Create: `src/orchestrator/ai/__init__.py`
- Create: `src/orchestrator/ai/safety.py`
- Create: `src/orchestrator/ai/llm.py`
- Create: `src/orchestrator/ai/planner.py`
- Test: `tests/test_ai_planner.py`

- [ ] Heuristic planner from open ports / prior results (works offline)
- [ ] LLM planner when `CERBERUS_LLM_BASE_URL` set; validate JSON schema
- [ ] Commit

### Task 5: Memory store

**Files:**
- Create: `src/orchestrator/ai/memory.py`
- Test: `tests/test_ai_memory.py`

- [ ] SQLite table `ai_memory` (id, target_hint, summary, embedding blob, created_at)
- [ ] `remember(summary, target_hint)`, `recall(query, k=3)`
- [ ] Commit

### Task 6: AI mission runner + dashboard APIs

**Files:**
- Create: `src/orchestrator/ai/runner.py`
- Modify: `src/orchestrator/dashboard.py` (`/api/run` accepts `ai_mode`, `nl_goal`, `confirm_high_risk`)
- Modify: `playbooks` optional — keep default
- Test: `tests/test_ai_runner.py`

- [ ] AI loop: plan → enqueue phase tools → collect → re-plan until stop/max steps
- [ ] Fallback to DecisionEngine/`build_phase_workflow` on planner failure
- [ ] Commit

### Task 7: Phase 5 confirm + audit APIs

**Files:**
- Modify: `src/orchestrator/ai/safety.py`, `mcp/actions.py`
- Add: `GET /api/ai/audit`, `GET /api/ai/sessions`
- Test: extend MCP/AI tests

- [ ] High-risk tools need `confirm=true` when confirm mode on
- [ ] Commit

### Task 8: Frontend AI Mode + activity

**Files:**
- Modify: `frontend/src/views/MissionControl.tsx`
- Modify: `frontend/src/api/client.ts`, `useMission.ts`
- Add: `frontend/src/components/AiModeToggle.tsx`
- Test: frontend unit if present
- Rebuild SPA

- [ ] AI Mode toggle + optional NL goal field
- [ ] Show planner reason / last AI actions when present in job status
- [ ] Commit

### Task 9: Docs + compose env

**Files:**
- Modify: `README.md` or `docs/...`
- Update: `docs/superpowers/specs/2026-07-20-ai-mcp-orchestration-design.md` (all phases)
- `.env.example` LLM + MCP keys

- [ ] Cursor MCP connect snippet
- [ ] Commit + push if requested

---

## Execution note

User requested prepare-all then implement-all. Execute Tasks 1→9 in this session with tests after each logical chunk; heuristic planner ensures CI works without Ollama.
