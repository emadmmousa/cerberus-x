# Human-Readable Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Show Mission Control results in plain English by default, with Advanced raw JSON for experts.

**Architecture:** Pure frontend `summarizeFinding` maps tool JSON → title/status/bullets; MissionSummary rollup; ResultCard/PhaseCard consume summaries. No backend changes.

**Tech Stack:** React, TypeScript, Vitest

## Global Constraints

- Frontend-only; do not change wrappers/DB/API payloads.
- Default view never dumps JSON or ANSI.
- Failures labeled Failed, not findings.
- Confirmed vulns only when explicit.

## File map

| File | Role |
| --- | --- |
| `frontend/src/lib/summarizeFinding.ts` | Tool → summary + rollup helpers |
| `frontend/src/components/MissionSummary.tsx` | Mission rollup panel |
| `frontend/src/components/ResultCard.tsx` | Human card + Advanced |
| `frontend/src/components/PhaseCard.tsx` | Friendly phase labels |
| `frontend/src/views/MissionControl.tsx` | Wire MissionSummary |
| `frontend/src/styles/global.css` | Minimal summary/card styles |
| `frontend/src/__tests__/summarizeFinding.test.ts` | Unit tests |

---

### Task 1: summarizeFinding + tests

- [ ] Write failing Vitest cases for nmap ports, empty ports, proxy timeout, sqlmap false, nuclei empty, nikto help text, ANSI strip, unknown fallback
- [ ] Implement `summarizeFinding`, `summarizeMission`, `PHASE_LABELS`, `stripAnsi`
- [ ] Tests green; commit

### Task 2: ResultCard + PhaseCard + MissionSummary

- [ ] Rewrite ResultCard to use summary by default
- [ ] Friendly PhaseCard labels + “N results”
- [ ] MissionSummary component + MissionControl wiring
- [ ] CSS tweaks; component tests; build SPA; commit

### Task 3: Verify + ship

- [ ] `npm test` + `npm run build`
- [ ] Restart compose orchestrator if needed
- [ ] Push to GitHub
