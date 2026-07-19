# Maximum Evasion Default Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing aggressive WAF-evasion profile the default for new unified missions.

**Architecture:** Keep the current evasion API and profile implementation. Change only the default playbook value and Mission Control initial state, while retaining all selectable levels.

**Tech Stack:** YAML, React, TypeScript, Vitest, Pytest

## Global Constraints

- Keep `off`, `low`, `medium`, `high`, and `aggressive` selectable.
- Use the existing `evasion_profile("aggressive")` behavior.
- Do not add dependencies.

---

### Task 1: Make aggressive evasion the default

**Files:**
- Modify: `playbooks/default.yaml:3`
- Modify: `frontend/src/views/MissionControl.tsx:21-23`
- Test: `frontend/src/__tests__/MissionControl.test.tsx`
- Test: `tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: `RunRequest.evasion`
- Produces: default launch request containing `evasion: "aggressive"`

- [ ] **Step 1: Update the frontend test expectation**

Change the expected launch body to:

```typescript
body: JSON.stringify({
  target: "test.com",
  use_proxy: true,
  proxy_protocol: "http",
  evasion: "aggressive",
})
```

- [ ] **Step 2: Add a playbook default assertion**

Extend `test_playbook_summary_lists_phases` with:

```python
assert data["evasion"] == "aggressive"
```

- [ ] **Step 3: Run focused tests and verify they fail**

Run:

```bash
source .venv/bin/activate
python -m pytest tests/test_dashboard_api.py -q
cd frontend && npx vitest run
```

Expected: both assertions fail because the current default is `medium`.

- [ ] **Step 4: Change both defaults**

In `playbooks/default.yaml`:

```yaml
evasion: "aggressive"
```

In `MissionControl.tsx`:

```typescript
const [evasion, setEvasion] = useState<
  "low" | "medium" | "high" | "aggressive" | "off"
>("aggressive");
```

- [ ] **Step 5: Run full verification**

Run:

```bash
source .venv/bin/activate
python -m pytest -q
cd frontend
npx vitest run
npm run build
```

Expected: 150 Python tests pass, 2 frontend tests pass, and Vite build succeeds.
