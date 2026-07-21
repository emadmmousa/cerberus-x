# Mission chat agent design

**Date:** 2026-07-21  
**Status:** Approved for planning  
**Product:** Firebreak

## Goal

Replace the empty Missions home with a ChatGPT/Claude-style agent that can propose and launch missions from natural-language prompts, while keeping a first-class **Manual** path on the same page.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Home layout | Full-page chat on `/missions`; mission list as side rail |
| Launch gate | Extract → **confirm card** → launch on approve |
| Manual path | Inline **Chat \| Manual** toggle (same page) |
| After launch | Stay on chat; compact **mission running** card; detail only on click |
| Architecture | Server-side chat sessions in Redis (Approach 2) |

## Layout & navigation

```
┌─────────────┬──────────────────────────────────────┐
│ Side rail   │  Main pane                           │
│ Missions    │  [ Chat | Manual ]                   │
│ · target…   │                                      │
│ · …         │  Chat: message thread + composer     │
│             │  Manual: existing NewMission fields  │
│ [New chat]  │                                      │
└─────────────┴──────────────────────────────────────┘
```

- Side rail lists org-scoped missions (status chip + target). Click opens `/missions/:id`.
- Default main pane is Chat mode.
- `/missions/new` redirects to `/missions?mode=manual` (bookmark-safe).
- Empty rail shows a short hint; chat/manual remain usable.
- Viewer role: read rail only; no composer, confirm launch, or manual start.

## Chat flow & APIs

### Redis model

- Key: `firebreak:chat:{chat_id}`
- Value: JSON `{ org_id, messages[], draft?, mission_ids[], updated_at }`
- TTL: 12 hours (aligned with session lifetime)
- Org-scoped; RBAC operator required to mutate when enforce is on

### Endpoints

1. `POST /api/chat/missions` → create thread `{ chat_id }`
2. `POST /api/chat/missions/{id}/messages` body `{ content }`  
   - Appends user message  
   - Calls Firebreak LLM with a **mission-intake** system prompt (not the kill-chain planner)  
   - Returns assistant text + optional `proposal`:
     ```json
     {
       "target": "string",
       "posture": "balanced|aggressive|defensive",
       "nl_goal": "string",
       "stealth": "off|low|high|null",
       "ready": true,
       "missing": []
     }
     ```
3. `POST /api/chat/missions/{id}/launch` body optional overrides from confirm card  
   - Requires `draft.ready`  
   - Applies existing `confirm_high_risk` rules for aggressive/non-defensive  
   - Reuses existing mission start path (`/api/run` / AI runner)  
   - Returns `{ task_id }` and clears/archives draft into a running card payload
4. `GET /api/chat/missions/{id}` → thread for refresh/reconnect

### Confirm card

Shown only when `proposal.ready === true`:

- Displays target, posture, goal (and stealth if set)
- **Launch** → launch endpoint  
- **Edit in Manual** → switch toggle to Manual, prefill fields from proposal  
- **Dismiss** → clear draft; stay in chat

One active draft per thread; a new ready proposal replaces the previous card.

### Manual mode

Same page; reuses today’s New Mission fields and launch helper (target, posture, AI mode, nl_goal, stealth, proxy options). No chat turn required.

### After launch

- Stay on `/missions` chat  
- Insert compact **mission running** card (task id, target, link to `/missions/:id`)  
- Side rail refreshes so the new mission appears  

## LLM behavior (intake agent)

- Purpose: clarify and extract mission parameters; **not** to run tools or plan kill-chain phases (that remains the Firebreak planner after launch).
- If target/scope missing or unauthorized → ask; **no** confirm card.
- On LLM down or invalid JSON: **keep asking / retrying toward a usable proposal**. Only if still unusable after that, respond with a soft fallback: *“I couldn’t parse that — switch to Manual or retry.”*
- Prefer asking one clarifying question at a time when `missing` is non-empty.

## Auth & audit

- Mutations require operator (or open lab when RBAC enforce is off).
- Audit events: `CHAT_MISSION_PROPOSE`, `CHAT_MISSION_LAUNCH` (and launch failure detail on confirm card, not navigation away).

## Errors & safety

- Launch failures surface on the confirm card; do not navigate away.
- Aggressive / high-risk keeps today’s `confirm_high_risk` gate on launch.
- Chat threads expire after 12h Redis TTL.

## Out of scope (v1)

- Full tool-calling general agent (Approach 3)
- Streaming token UI (may add later; v1 can be request/response turns)
- Multi-mission batch from one prompt
- Replacing Mission Detail or AI Lab pages

## Testing

- API: propose → confirm payload; launch → `task_id`; RBAC deny for viewer
- UI: Chat|Manual toggle; confirm Launch / Dismiss / Edit in Manual; running card link
- Redirect `/missions/new` → `?mode=manual`
- No session/Werkzeug regressions on `/missions` (binary Redis session client remains)

## Implementation notes

- Frontend: evolve `Missions.tsx` into shell (rail + mode toggle + chat/manual panes); extract manual form from `NewMission.tsx` for reuse.
- Backend: new blueprint `orchestrator/api/chat_missions.py` (or similar); thin wrapper around existing run/AI start.
- Preserve Firebreak branding and `FIREBREAK_*` / `firebreak:*` conventions.
