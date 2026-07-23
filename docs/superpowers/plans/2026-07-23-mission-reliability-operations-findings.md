# Mission Reliability, Operations, and Findings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authorized-target missions preflight reliably, expose readiness and lifecycle control to operators, close MCP authorization parity, and deliver normalized findings.

**Architecture:** Add small, pure readiness and findings services behind existing Flask blueprints. Reuse `mission_svc` for organization-scoped lifecycle transitions, `celery_errors` for registration inspection, and `enforce_launch_authorization` for every enqueue path. React consumes typed API payloads through the existing client and Mission Control components.

**Tech Stack:** Python 3.14, Flask, Celery, Redis-backed job store, SQLite, React, TypeScript, Vitest, pytest.

## Global Constraints

- All launch and MCP tool actions must pass RBAC and `enforce_launch_authorization`.
- `FIREBREAK_REQUIRE_AUTHZ=false` retains existing allow semantics.
- Readiness responses classify `ready`, `stale`, and `unreachable`; unreachable is not treated as stale.
- No job record may be created when preflight fails.
- Lifecycle actions stay organization-scoped and audit every state-changing action.
- Cancellation must not claim a running external subprocess stopped unless its task is revoked.
- Findings preserve raw evidence pointers and deduplicate by stable fingerprint.

---

## File Structure

- Modify `src/orchestrator/celery_errors.py`: readiness payloads and preflight error type.
- Modify `src/orchestrator/api/missions.py`: preflight, readiness endpoint, lifecycle endpoints.
- Modify `src/orchestrator/mcp/actions.py`: target authorization and tool-specific preflight.
- Modify `src/orchestrator/services/missions.py`: cancellation and retry transition service.
- Create `src/orchestrator/findings.py`: normalization, fingerprinting, persistence/query/export service.
- Modify `src/orchestrator/database.py`: findings schema and repository helpers.
- Modify `src/orchestrator/api/results.py`: organization-scoped findings and export endpoints.
- Modify `frontend/src/api/client.ts`: readiness, lifecycle, and findings DTOs/calls.
- Modify `frontend/src/components/OperationsCommandBar.tsx`, `frontend/src/views/Missions.tsx`: readiness chip.
- Modify `frontend/src/views/MissionDetail.tsx`: lifecycle controls and findings timeline.
- Create focused backend and frontend tests listed per task.

### Task 1: Readiness service and synchronous launch preflight

**Files:**
- Modify: `src/orchestrator/celery_errors.py`
- Modify: `src/orchestrator/api/missions.py`
- Modify: `src/orchestrator/api/chat_missions.py`
- Create: `tests/test_worker_readiness.py`
- Modify: `tests/test_dashboard_api.py`

**Interfaces:**
- Produces `worker_readiness(timeout: float = 3.0) -> dict[str, object]`.
- Produces `GET /api/workers/readiness`.

- [ ] **Step 1: Write failing readiness tests**

```python
def test_worker_readiness_marks_unreachable(monkeypatch):
    monkeypatch.setattr("orchestrator.celery_errors._worker_registered_tasks", lambda timeout: None)
    assert worker_readiness()["status"] == "unreachable"

def test_api_run_preflight_failure_creates_no_job(monkeypatch, client):
    monkeypatch.setattr("orchestrator.api.missions.assert_full_arsenal_ready",
                        lambda: (_ for _ in ()).throw(RuntimeError("missing task")))
    before = set(playbook_jobs)
    response = client.post("/api/run", json={"target": "authorized.example"})
    assert response.status_code == 503
    assert response.get_json()["reason"] == "worker_preflight_failed"
    assert set(playbook_jobs) == before
```

- [ ] **Step 2: Run the readiness tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_worker_readiness.py -q`  
Expected: FAIL because `worker_readiness` and the 503 mapping do not exist.

- [ ] **Step 3: Implement the readiness payload and preflight mapping**

```python
def worker_readiness(timeout: float = 3.0) -> dict[str, object]:
    registered = _worker_registered_tasks(timeout=timeout)
    expected = unique_task_map_celery_names()
    if registered is None:
        return {"status": "unreachable", "expected_count": len(expected), "missing_tasks": []}
    missing = sorted(expected - registered)
    return {
        "status": "stale" if missing else "ready",
        "expected_count": len(expected),
        "missing_tasks": missing,
        "message": format_missing_celery_tasks_error(missing) if missing else "Workers ready",
    }
```

Call `assert_full_arsenal_ready()` in `api_run()` before `create_job_record()` and return
`{"error": str(exc), "reason": "worker_preflight_failed"}`, HTTP 503 on `RuntimeError`.
Add `@missions_bp.get("/api/workers/readiness")` guarded by `Role.VIEWER`.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_worker_readiness.py tests/test_dashboard_api.py tests/test_chat_missions.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/celery_errors.py src/orchestrator/api/missions.py \
  src/orchestrator/api/chat_missions.py tests/test_worker_readiness.py tests/test_dashboard_api.py
git commit -m "feat(missions): add worker readiness preflight"
```

### Task 2: MCP authorization and tool-specific readiness

**Files:**
- Modify: `src/orchestrator/mcp/actions.py`
- Modify: `src/orchestrator/mcp/blueprint.py`
- Modify: `docs/SECURITY_AND_AUTH.md`
- Modify: `tests/test_mcp_actions.py`
- Modify: `tests/test_mcp_http.py`

**Interfaces:**
- `enqueue_tool()` raises `PermissionError` before `.delay()` for denied targets or stale requested tools.
- JSON-RPC maps authorization denials to a structured forbidden error and preflight failures to unavailable.

- [ ] **Step 1: Write failing MCP enforcement tests**

```python
def test_enqueue_tool_denies_off_list_target(authz_file, monkeypatch):
    monkeypatch.setenv("FIREBREAK_REQUIRE_AUTHZ", "true")
    with pytest.raises(PermissionError, match="authorized-target"):
        enqueue_tool(session_id=session_id, tool="nmap", target="offlist.example")

def test_enqueue_tool_checks_requested_worker_task(monkeypatch):
    monkeypatch.setattr("orchestrator.mcp.actions.assert_workers_ready",
                        lambda names: (_ for _ in ()).throw(RuntimeError("stale")))
    with pytest.raises(RuntimeError, match="stale"):
        enqueue_tool(session_id=session_id, tool="nmap", target="authorized.example")
```

- [ ] **Step 2: Run MCP tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_mcp_actions.py tests/test_mcp_http.py -q`  
Expected: FAIL because `enqueue_tool()` does not enforce target or worker registration.

- [ ] **Step 3: Implement before-enqueue checks**

```python
from scanner import enforce_launch_authorization
from orchestrator.celery_errors import assert_workers_ready

enforce_launch_authorization(target, path="mcp.run_tool")
assert_workers_ready([tool])
```

Place them after target/tool validation and before `_TASK_MAP[tool].delay(...)`.
Map `PermissionError` to HTTP/JSON-RPC forbidden and `RuntimeError` to service unavailable in the MCP blueprint.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_mcp_actions.py tests/test_mcp_http.py tests/test_authorization_gate.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/mcp/actions.py src/orchestrator/mcp/blueprint.py \
  docs/SECURITY_AND_AUTH.md tests/test_mcp_actions.py tests/test_mcp_http.py
git commit -m "fix(mcp): enforce target and worker preflight"
```

### Task 3: Worker readiness command-bar visibility

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/OperationsCommandBar.tsx`
- Modify: `frontend/src/views/Missions.tsx`
- Create: `frontend/src/__tests__/WorkerReadinessChip.test.tsx`

**Interfaces:**
- `getWorkerReadiness(): Promise<WorkerReadiness>`.
- `WorkerReadinessChip` renders `ready`, `stale`, or `unreachable` with remediation text.

- [ ] **Step 1: Write a failing chip test**

```tsx
it("renders stale worker remediation", () => {
  render(<WorkerReadinessChip readiness={{ status: "stale", missing_tasks: ["run_nmap_task"] }} />);
  expect(screen.getByText(/workers stale/i)).toBeInTheDocument();
  expect(screen.getByText(/run_nmap_task/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the frontend test**

Run: `cd frontend && npm test -- --run src/__tests__/WorkerReadinessChip.test.tsx`  
Expected: FAIL because the component and client DTO do not exist.

- [ ] **Step 3: Implement the client and chip**

```ts
export type WorkerReadiness = {
  status: "ready" | "stale" | "unreachable";
  expected_count: number;
  missing_tasks: string[];
  message: string;
};

export function getWorkerReadiness() {
  return apiJson<WorkerReadiness>("/api/workers/readiness");
}
```

Poll only while the Missions view is visible, surface a chip in
`OperationsCommandBar`, and show the API `message` in a native `<details>`
disclosure. Do not block rendering when the endpoint fails.

- [ ] **Step 4: Run focused frontend tests**

Run: `cd frontend && npm test -- --run src/__tests__/WorkerReadinessChip.test.tsx src/__tests__/MissionControl.test.tsx`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/OperationsCommandBar.tsx \
  frontend/src/views/Missions.tsx frontend/src/__tests__/WorkerReadinessChip.test.tsx
git commit -m "feat(ops): show worker readiness in missions"
```

### Task 4: Mission cancellation and retry lifecycle

**Files:**
- Modify: `src/orchestrator/services/missions.py`
- Modify: `src/orchestrator/api/missions.py`
- Modify: `src/orchestrator/ai/runner.py`
- Modify: `src/orchestrator/dashboard.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/MissionDetail.tsx`
- Create: `tests/test_mission_lifecycle.py`
- Create: `frontend/src/__tests__/MissionLifecycleControls.test.tsx`

**Interfaces:**
- `request_cancel(job_id) -> {"task_id", "state", "revoked_task_ids"}`.
- `retry_mission(job_id) -> {"task_id", "retried_from", "state"}`.
- `POST /api/missions/<job_id>/cancel`, `POST /api/missions/<job_id>/retry`.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_request_cancel_revokes_phase_tasks_and_is_org_scoped(monkeypatch):
    job = create_fixture_job(state="STARTED", phases=[{"task_id": "phase-1"}])
    revoked = []
    monkeypatch.setattr("celery.result.AsyncResult.revoke", lambda self, **kw: revoked.append(self.id))
    assert request_cancel(job["task_id"])["state"] == "CANCEL_REQUESTED"
    assert "phase-1" in revoked

def test_retry_rejects_non_retryable_mission():
    job = create_fixture_job(state="SUCCESS")
    with pytest.raises(ValueError, match="not retryable"):
        retry_mission(job["task_id"])
```

- [ ] **Step 2: Run lifecycle tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_mission_lifecycle.py -q`  
Expected: FAIL because the lifecycle API does not exist.

- [ ] **Step 3: Implement state transitions**

```python
RETRYABLE_STATES = {"FAILURE"}

def request_cancel(job_id: str) -> dict[str, Any]:
    job = get_mission(job_id)
    if job.get("state") not in {"PENDING", "STARTED"}:
        raise ValueError("mission is not cancellable")
    # revoke every known phase task, persist CANCEL_REQUESTED, audit action

def retry_mission(job_id: str) -> dict[str, Any]:
    job = get_mission(job_id)
    if job.get("state") not in RETRYABLE_STATES:
        raise ValueError("mission is not retryable")
    # delegate to restart_mission and set retried_from on the new job
```

Make the runner stop scheduling additional phases when `cancel_requested` is
true; have it finalize state `CANCELLED` after its current collection returns.

- [ ] **Step 4: Implement API and UI controls**

Add RBAC `Role.OPERATOR` endpoints. Add Cancel only for `PENDING`/`STARTED`
missions and Retry only for `FAILURE`, reflecting returned state in Mission
Detail without claiming a running command was terminated.

- [ ] **Step 5: Run focused tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_mission_lifecycle.py tests/test_rbac_missions.py -q && cd frontend && npm test -- --run src/__tests__/MissionLifecycleControls.test.tsx`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator/services/missions.py src/orchestrator/api/missions.py \
  src/orchestrator/ai/runner.py src/orchestrator/dashboard.py frontend/src/api/client.ts \
  frontend/src/views/MissionDetail.tsx tests/test_mission_lifecycle.py \
  frontend/src/__tests__/MissionLifecycleControls.test.tsx
git commit -m "feat(missions): add cancel and retry controls"
```

### Task 5: Normalized findings, filters, and exports

**Files:**
- Create: `src/orchestrator/findings.py`
- Modify: `src/orchestrator/database.py`
- Modify: `src/orchestrator/reporting.py`
- Modify: `src/orchestrator/api/results.py`
- Modify: `src/orchestrator/dashboard.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/MissionDetail.tsx`
- Create: `tests/test_findings.py`
- Create: `frontend/src/__tests__/MissionFindings.test.tsx`

**Interfaces:**
- `ingest_findings(job_id, target, phase, rows) -> list[dict]`.
- `list_findings(job_id=None, target=None, severity=None, limit=50, offset=0)`.
- `GET /api/findings`, `GET /api/missions/<job_id>/findings/export?format=json|markdown`.

- [ ] **Step 1: Write failing normalization tests**

```python
def test_ingest_deduplicates_same_template_and_endpoint(db):
    first = ingest_findings("job-1", "authorized.example", "vuln", [
        {"tool": "nuclei", "findings": [{"template_id": "CVE-1", "title": "CVE", "severity": "high", "matched_at": "https://authorized.example/a"}]}
    ])
    second = ingest_findings("job-2", "authorized.example", "vuln", [
        {"tool": "nuclei", "findings": [{"template_id": "CVE-1", "title": "CVE", "severity": "high", "matched_at": "https://authorized.example/a"}]}
    ])
    assert first[0]["fingerprint"] == second[0]["fingerprint"]
    assert len(list_findings(target="authorized.example")) == 1
```

- [ ] **Step 2: Run findings tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_findings.py -q`  
Expected: FAIL because the normalized finding repository does not exist.

- [ ] **Step 3: Implement finding normalization and persistence**

```python
def finding_fingerprint(target: str, tool: str, finding: dict[str, Any]) -> str:
    identity = "|".join([
        normalize_target(target),
        str(finding.get("template_id") or tool).lower(),
        str(finding.get("title") or "").strip().lower(),
        str(finding.get("matched_at") or finding.get("endpoint") or finding.get("port") or ""),
    ])
    return hashlib.sha256(identity.encode()).hexdigest()
```

Persist first/last observed times, severity, confidence, source tools, mission
IDs, and raw-result evidence references. Call `ingest_findings` after phase
results are saved, then expose organization-scoped query and JSON/Markdown
export endpoints.

- [ ] **Step 4: Implement findings UI**

Render a severity-first timeline in Mission Detail. Add filters for severity
and target only where the corresponding API supports them. Export controls use
the server-produced JSON/Markdown payload and show an explicit empty state.

- [ ] **Step 5: Run focused tests**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_findings.py tests/test_results_api.py -q && cd frontend && npm test -- --run src/__tests__/MissionFindings.test.tsx`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator/findings.py src/orchestrator/database.py src/orchestrator/reporting.py \
  src/orchestrator/api/results.py src/orchestrator/dashboard.py frontend/src/api/client.ts \
  frontend/src/views/MissionDetail.tsx tests/test_findings.py \
  frontend/src/__tests__/MissionFindings.test.tsx
git commit -m "feat(findings): add normalized mission evidence"
```

## Final Verification

- [ ] Run backend suite:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q -p no:cacheprovider --ignore=tests/chaos
```

- [ ] Run frontend suite and production build:

```bash
cd frontend && npm test -- --run && npm run build
```

- [ ] Push only after every task has passed and commits use Conventional Commit subjects:

```bash
git push origin HEAD
```
