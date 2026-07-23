# Firebreak — Missions & Chat Agent

Deep dive into playbooks, the AI loop, and the conversational mission planner.

---

## Mission Types

| Type | Trigger | Planner |
|------|---------|---------|
| **Static playbook** | Manual launch with YAML file | None — phases fixed in YAML |
| **AI adaptive** | Manual + AI mode, or AI-heavy chat | `run_ai_mission()` + DecisionEngine |
| **Chat proposal** | Chat confirm → launch | Intake builds `seed_plan`; may use AI runner |
| **OSINT-only** | OSINT deck / chat | Restricted tool set; person-centric seeds |

---

## Playbook Structure

YAML files in `playbooks/`:

```yaml
name: Example Mission
posture: aggressive
phases:
  - name: recon
    parallel: true
    tools:
      - name: nmap
        args: "-sV -T4"
      - name: subfinder
    when:
      always: true
  - name: exploit
    depends_on: recon
    tools:
      - name: metasploit
        args: "..."
    when:
      open_ports: [445, 3389]
```

### Phase attributes

| Key | Meaning |
|-----|---------|
| `name` | Phase identifier |
| `tools` | List of `{name, args}` Celery tasks |
| `parallel` | Run tools as Celery `group` vs `chain` |
| `depends_on` | Prior phase must complete |
| `when` | DecisionEngine conditions on prior results |
| `evasion` | WAF profile override |

Target substitution: `{{target}}` in args is replaced at enqueue time.

---

## Execution Pipeline

```
1. create_job(job_id, target, playbook, posture, …)
2. For each phase (respecting depends_on + when):
     build_phase_workflow(phase, target, parallel, proxy, evasion)
     → Celery group or chain of wrapper tasks
3. Workers run tools → save_phase_result()
4. DecisionEngine.evaluate_phase() → optional auto follow-ons
5. Mirror status to Redis + emit Socket.IO events
6. Mark job complete / failed
```

AI missions insert **dynamic phases** between static ones when the planner proposes new steps.

---

## AI Adaptive Loop (`run_ai_mission`)

Located in `src/orchestrator/ai/runner.py`:

```
while steps < max_steps and not complete:
  plan = planner.propose_next_phase(context, posture, findings)
  if plan is empty: break
  execute plan.tools via Celery
  merge results into context
  decision_engine.evaluate_phase(...)
  optionally update blackboard
```

### Planner inputs

- Current target and posture
- Prior phase summaries (truncated)
- Open ports, CVEs, tool failures
- Allowlisted tool names for posture

### Planner outputs

JSON structure:

```json
{
  "phase_name": "web_exploit",
  "tools": [{"name": "sqlmap", "args": "--batch ..."}],
  "rationale": "SQL error detected in httpx probe"
}
```

Fallback heuristics in `planner.py` when LLM is unreachable.

---

## Chat Agent Architecture

### Components

| Module | Role |
|--------|------|
| `chat/store.py` | Thread messages, drafts, metadata |
| `chat/intake.py` | Streaming advisor, proposal detection, launch |
| `chat/targets.py` | Target normalization from text |
| `osint/seeds.py` | Email/domain/username/name seed extraction |
| `api/chat_missions.py` | HTTP: create, stream, launch, list |

### Advisor stream

`POST /api/chat/missions/<id>/stream`:

1. Append user message to thread.
2. Build system prompt with posture, catalog snippets, optional web search.
3. Stream LLM tokens to client (SSE).
4. Parse completed message for ` ```firebreak-plan` fenced JSON.
5. Run `detect_proposal()` → store draft on thread.

### Proposal object

Contains:

- `target` — hostname, URL, or OSINT subject label
- `posture` — aggressive / balanced / defensive
- `playbook` or inline `tools`
- `osint_seeds` — structured seed list for intel missions
- `auto_execute` — skip confirm when safe and complete

### Launch detection

Messages matching launch acknowledgements:

- "yes", "confirmed", "launch", "go", "do it", …

**Critical behavior:** Single-word acks are **not** parsed as OSINT usernames (`@confirmed`). `resolve_osint_seeds_for_chat()` walks prior user messages to recover the real target (including Arabic full names).

### Launch execution

`POST /api/chat/missions/<id>/launch`:

1. Load draft proposal from thread.
2. Authorization check (if `FIREBREAK_REQUIRE_AUTHZ`).
3. `_execute_chat_mission()` → builds plan → `POST /api/run` equivalent internally.
4. Return `job_id` → frontend navigates to mission detail.

---

## `firebreak-plan` Block Format

Embedded in advisor markdown:

````markdown
```firebreak-plan
{
  "target": "corp.example",
  "posture": "balanced",
  "playbook": "balanced_offense_defense.yaml",
  "summary": "Recon and vuln scan of corp.example",
  "osint_seeds": []
}
```
````

Intake validates JSON, merges OSINT seeds from thread, and presents confirmation UI.

---

## OSINT Chat Flow (Two-Turn)

Many OSINT strike templates ship **without** a baked-in target:

```
Turn 1 — User: [clicks "OSINT Person Deck"]
Turn 1 — Advisor: proposes OSINT-only plan, asks for target

Turn 2 — User: "عبدالباسط هارون الشهيبي"  (or email/domain/@user)
Turn 2 — Advisor: updated proposal with seeds

Turn 3 — User: "Confirmed"
Turn 3 — System: launches with resolved seeds (not @confirmed)
```

Implementation: `is_launch_ack_message()`, `extract_followup_osint_seeds()`, `_thread_target()` skipping acks.

---

## DecisionEngine Interaction

After each executed phase (playbook or AI):

| Signal | Typical follow-on |
|--------|-------------------|
| Open 80/443 | httpx, nuclei, nikto |
| SQLi indicators | sqlmap |
| SMB open | crackmapexec, impacket |
| MSF module success | Session handling on blackboard |
| Defensive posture | Hardening notes, no exploit tools |

Chat-launched missions use the same engine once execution starts.

---

## Job State & Observability

| Field | Source |
|-------|--------|
| `status` | pending / running / complete / failed / stopped |
| `current_phase` | Redis mirror |
| `phases[]` | Per-tool status + result IDs |
| `ai_steps` | Planner iteration count |
| `error` | Last failure message |

Frontend: `useMission.ts` combines polling + Socket.IO.

---

## Stopping & Editing

- **Stop:** `POST /api/missions/<id>/stop` — revokes Celery tasks where possible.
- **Edit metadata:** Patch target notes or labels without re-running completed phases (API-dependent).

---

## CLI Parity

```bash
python -m orchestrator.cli run \
  --playbook playbooks/balanced_offense_defense.yaml \
  --target https://juice-shop.example \
  --posture balanced \
  --ai
```

Chat missions are UI-first but produce the same underlying job records as `/api/run`.

---

## Related

- [OSINT_INTEL.md](OSINT_INTEL.md) — Seeds and breach tooling
- [ARCHITECTURE.md](ARCHITECTURE.md) — Celery and storage
- [USER_JOURNEYS.md](USER_JOURNEYS.md) — Operator steps
