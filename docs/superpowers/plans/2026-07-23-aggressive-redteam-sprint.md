# Aggressive Red-Team Sprint — 8-Hour Plan

> **For agentic workers:** Execute phases in order; run tests after each phase.

**Goal:** Harden Firebreak into the most capable *authorized* aggressive web red-team console — chat-driven strike planning, full arsenal execution, operator gates where safety requires them.

**Architecture:** Chat → intent/cognition → compile → confirm → preflight workers → AI runner with adaptive escalation + tool invention. Frontend surfaces confirm, OSINT, worker health on Ops.

**Tech Stack:** Flask, Celery, React/Vite, Ollama LLM, Redis

## Global Constraints

- Authorized scope only — no bypass/jailbreak/criminal payloads in prompts or docs
- Minimize diff per task; match existing patterns
- Conventional Commits when user asks to commit

---

## Phase 1 — Operator UX & launch reliability (0–2h)

- [ ] Mission confirm card open when plan pending; sticky launch banner
- [ ] OSINT seeds on main Chat tab (`Missions.tsx`)
- [ ] Worker arsenal preflight at chat mission launch (`chat_missions.py`)
- [ ] Authz inline recovery button in `MissionChat`
- [ ] Strike library accessible from chromeless chat

## Phase 2 — Chat agent intelligence (2–4h)

- [ ] Cerberus commands route through proposal/compile when target present
- [ ] Tighten launch ack regex (`go`/`start` only as whole words in short messages)
- [ ] Advisor validates firebreak-plan on execute intent
- [ ] Fix `httpx` invention binary → `httpx`

## Phase 3 — New authorized strike tools (4–6h)

- [ ] `waf-bypass-probe` custom wrapper (ffuf/sqlmap evasion bundle)
- [ ] `jwt-forge` scaffold recipe (httpx + arjun + nuclei)
- [ ] `api-strike` scaffold (katana + arjun + ffuf + nuclei)
- [ ] Wire into `attack_methods.py` aggressive rotation

## Phase 4 — CI & tests (6–7h)

- [ ] Expand `.github/workflows/ci.yml` chat/adaptive/registry tests
- [ ] Add `npm run build` to CI
- [ ] `MissionChat.test.tsx` confirm + launch_error cases

## Phase 5 — Ops visibility (7–8h)

- [ ] Worker health chip on Missions command bar
- [ ] Landing CTA for logged-in → `/missions`

---

## Verification

```bash
cd frontend && npm test -- --run && npm run build
PYTHONPATH=src .venv/bin/python -m pytest tests/test_chat_*.py tests/test_celery_errors.py tests/test_scaffold_tools.py -q
```
