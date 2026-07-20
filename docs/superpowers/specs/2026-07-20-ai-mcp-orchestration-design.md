# AI Orchestration (MCP + AI Modes) Design — Phases 1–5

Supersedes the Phase-1-only preview in earlier drafts. Approved decisions for Phase 1 remain; Phases 2–5 are in scope for the full implementation pass.

## Decisions

| Topic | Choice |
| --- | --- |
| Order | Build MCP → planner → memory → NL/dynamic → safety/UI in one delivery |
| MCP host | Flask orchestrator (`/mcp`); extract later if needed |
| Transport | HTTP JSON-RPC at `POST /mcp` (+ optional `GET /mcp/sse`) |
| Auth | API key + `session_id` |
| LLM | OpenAI-compatible (`CERBERUS_LLM_BASE_URL`); **heuristic fallback** when unset/down |
| High-risk | Confirm required when `CERBERUS_AI_REQUIRE_CONFIRM=true` (default on for AI/MCP) |
| Playbooks | Default path unchanged when `ai_mode` false |

## Phase map

| Phase | Deliverable |
| --- | --- |
| 1 | MCP tools: session, list_tools, run_tool, status, findings, list_sessions |
| 2 | AI planner + `ai_mode` mission loop + LLM optional |
| 3 | Mission memory recall/remember (SQLite) |
| 4 | NL goal → plan; dynamic tool selection from findings; retry hints |
| 5 | Confirm gate, audit APIs, Mission Control AI Mode UI |

## Architecture

```text
UI (AI Mode / NL goal) ──┐
MCP client ──────────────┼──► Flask
                         │     ├── /mcp (JSON-RPC)
                         │     ├── /api/run (ai_mode?)
                         │     └── ai.planner + ai.memory
                         ▼
                    Redis sessions/audit
                         ▼
                    Celery _TASK_MAP → wrappers
                         ▼
                    SQLite results + ai_memory
```

See implementation plan: `docs/superpowers/plans/2026-07-20-ai-mcp-orchestration.md`.
