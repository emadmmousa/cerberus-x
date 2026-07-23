# Mission Reliability, Operations, and Findings Design

## Goal

Deliver three connected improvements for authorized-target engagements:

1. make worker and arsenal readiness visible before launch;
2. give operators safe, auditable lifecycle control over running missions;
3. turn raw results into deduplicated, evidence-backed findings ready for review
   and export.

This design does not introduce tools, scaffolds, targets, or capabilities beyond
the existing authorized assessment arsenal.

## Constraints

- Every launch and tool action remains subject to RBAC and
  `enforce_launch_authorization`.
- `FIREBREAK_REQUIRE_AUTHZ=false` retains its existing no-op allowlist
  semantics; enabled enforcement denies off-list targets before work is queued.
- Worker discovery must distinguish an unavailable broker from a stale worker
  missing registered task names.
- Lifecycle actions are scoped to the mission's organization and recorded in the
  audit trail.
- A cancellation request must revoke queued Celery work where possible, record a
  terminal cancellation state, and never imply that already-running subprocesses
  stopped successfully.

## Architecture

### Shared readiness service

`orchestrator.celery_errors` remains the source of truth for worker task
registration. A small readiness payload will expose:

- `status`: `ready`, `stale`, or `unreachable`;
- expected and missing Celery task names;
- derived `scaffold_count` and CLI-wrapper count;
- operator remediation text.

`GET /api/workers/readiness` returns this payload without enqueuing a health
probe. It is a bounded, short-timeout check intended for the command bar and
launch preflight.

Chat and manual mission launch use full-arsenal preflight before creating a job
record. MCP `run_tool` performs a tool-specific registration preflight before
enqueueing. A stale worker produces a structured 503 response with
`reason: worker_preflight_failed`, so no phantom `PENDING` mission is created.

### Mission lifecycle control

Mission state is extended through a lifecycle service rather than mutating
`playbook_jobs` directly from HTTP controllers. It provides:

- `request_cancel(job_id)`: verifies organization access, marks cancellation
  requested, revokes the phase task IDs already stored on the job, and records
  an audit event;
- `mark_cancelled(job_id)`: finalizes cancellation only after the runner stops
  scheduling work;
- `retryable(job_id)`: identifies failures caused by worker availability or
  collection timeout, never reusing an authorization-denied job;
- `retry(job_id)`: creates a new mission with the original authorized launch
  inputs and an audit link to the source job.

The existing runner checks for a cancellation request before scheduling each
phase and after collecting results. It stops further escalation but preserves
already-collected evidence.

The UI adds an active-mission control surface: Cancel for running work, Retry
for retryable failures, and explicit state copy. It does not expose Resume as a
pretend continuation; retry begins a separate, auditable mission.

### Findings workflow

A finding is a normalized record derived from a mission result, with:

- stable fingerprint: target + normalized tool/template + title + affected
  endpoint/port;
- severity, confidence, title, source tools, first/last observed timestamps;
- evidence pointers to raw phase results, never destructive replacement of raw
  data;
- mission and organization IDs.

Ingestion is idempotent: repeated results with the same fingerprint update the
existing finding's observation metadata rather than generating duplicates.
The findings API supports mission and target filters, severity filtering, and
cursor/offset pagination following existing list conventions.

The Mission Detail page renders a findings timeline ordered by severity and
recency. Export produces JSON and Markdown from normalized records plus the
linked evidence summary; it must label unavailable evidence rather than invent
it.

### MCP authorization parity

MCP `run_tool` calls `enforce_launch_authorization` before enqueueing. The
response uses a structured JSON-RPC authorization error, and the denied attempt
is audited. This gives MCP the same target-scope guarantees as chat and HTTP
mission APIs.

## User Experience

The Missions command bar displays a compact worker chip:

- green: all registered executors ready;
- amber: worker reachable but one or more task registrations are missing;
- neutral/gray: readiness cannot be determined;
- selecting the chip opens remediation text and links to the detailed Arsenal
  view.

Manual launch displays preflight failures inline and does not navigate to a
mission page when a job was not created.

Mission Detail shows lifecycle state, cancellation/retry controls, and the
findings timeline. Controls are hidden or disabled when the current role or
mission state does not permit the action.

## Error Handling

- Unauthorized targets: 403, `reason: unauthorized_target`; never enqueue work.
- Worker preflight failure: 503, `reason: worker_preflight_failed`; never
  create a job.
- Readiness transport failure: reported as `unreachable`, not as a definitive
  stale registration set.
- Invalid lifecycle transition: 409 with the current state.
- Cross-organization lifecycle access: existing RBAC/org error behavior.
- Export with no findings: 200 with a valid empty report and a clear summary.

## Testing

### Backend

- readiness payload classifies ready, stale, and unreachable workers;
- `/api/run` and chat deny a stale arsenal before job creation; MCP denies a
  stale requested tool before enqueueing;
- MCP denies off-list targets when authorization is enabled;
- cancellation prevents later phases and records an audit event;
- retry creates a new linked mission only for retryable failures;
- finding fingerprinting deduplicates repeated results while retaining evidence;
- findings filters, pagination, and exports preserve organization boundaries.

### Frontend

- worker chip state and remediation rendering;
- manual preflight error display;
- lifecycle controls call the correct endpoints and reflect terminal state;
- findings severity/order/filter display and empty-state export behavior.

### Verification

Run focused backend and frontend suites during each increment, then:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests -q -p no:cacheprovider --ignore=tests/chaos
cd frontend && npm test -- --run && npm run build
```

## Delivery Order

1. launch preflight parity and worker readiness API/chip;
2. MCP authorization parity;
3. cancellation and retry lifecycle APIs plus controls;
4. normalized findings ingestion, APIs, detail UI, and exports.

This order prevents new control and reporting surfaces from obscuring stale
worker or unauthorized-target failures.
