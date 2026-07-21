# Mission Chat Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full-page mission chat on `/missions` with confirm-then-launch, side-rail history, and inline Manual mode.

**Architecture:** Redis-backed chat threads (`firebreak:chat:{id}`); intake LLM extracts proposal JSON; launch reuses existing `/api/run` AI/playbook start path; Missions UI becomes rail + Chat|Manual panes.

**Tech Stack:** Flask blueprints, Redis, existing `chat_completion`, React + Vite SPA.

## Global Constraints

- Firebreak branding only (`FIREBREAK_*`, `firebreak:*`, no Cerberus)
- Operator role for chat mutate/launch when RBAC enforce is on
- Confirm card required before launch; stay on chat after launch
- LLM fallback: keep asking toward a solution; then Manual/retry message
- 12h Redis TTL on chat threads

---

## File map

| File | Responsibility |
|------|----------------|
| `src/orchestrator/chat/store.py` | Redis CRUD for chat threads |
| `src/orchestrator/chat/intake.py` | Intake prompt + parse proposal |
| `src/orchestrator/api/chat_missions.py` | HTTP API |
| `src/orchestrator/api/__init__.py` | Register blueprint |
| `tests/test_chat_missions.py` | API + store tests |
| `frontend/src/views/Missions.tsx` | Shell: rail + mode toggle |
| `frontend/src/components/MissionChat.tsx` | Chat thread UI |
| `frontend/src/components/ManualMissionForm.tsx` | Extracted from NewMission |
| `frontend/src/api/client.ts` | Chat API helpers |
| `frontend/src/routes.tsx` | `/missions/new` → `?mode=manual` |

---

### Task 1: Chat store + intake (TDD)

- [ ] Write failing tests for create/get/append/TTL key prefix
- [ ] Implement `store.py` + `intake.py` (heuristic + LLM)
- [ ] Verify tests pass

### Task 2: Chat missions API (TDD)

- [ ] Write failing tests: create, message→proposal, launch→task_id, dismiss draft
- [ ] Implement `chat_missions.py`; register blueprint
- [ ] Launch via shared mission start (ai_mode true by default for chat)
- [ ] Verify tests pass

### Task 3: Frontend shell

- [ ] Extract `ManualMissionForm` (optional navigateOnLaunch=false)
- [ ] Rebuild `Missions.tsx` with rail + Chat|Manual
- [ ] `MissionChat` with confirm card + running card
- [ ] Redirect `/missions/new`
- [ ] Client API helpers + light CSS
- [ ] `npm test` / build into static

### Task 4: Verify live

- [ ] Restart/reload orchestrator; smoke `/api/chat/missions` and UI
