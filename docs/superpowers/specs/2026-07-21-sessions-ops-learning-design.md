# Sessions, Ops Toggles, Bulk Examples & Scheduled Learning — Design

**Date:** 2026-07-21  
**Status:** Approved for planning  
**Repo:** Cerberus-X / Firebreak

## Problem

Five operator needs land together:

1. **Per-user sessions** — today Flask uses signed cookies with a hardcoded `SECRET_KEY` fallback and no server-side store; replicas and multi-user logins share fragile cookie-only state.
2. **Bulk load examples** — Mission Control’s Dataset contribute UI loads one seed example at a time; operators need “load all for this posture” and submit them in one pass.
3. **Automatic ML (daily)** — contributions and posture seeds should merge and evaluate every day without a manual script run.
4. **AI agent learning tick (every minute)** — harvest completed missions into training pairs and keep scaffold health/latency warm; not a GPU train loop.
5. **Admin Ops toggles** — Auto-Scale, Auto-Train, and Learning Tick must be flipable On / Off / Defer-to-env from the Admin console (same pattern as RBAC enforce).

## Goals

- Server-side Redis sessions so each authenticated user has an isolated, revokeable session that works across orchestrator replicas.
- FirebreakPanel: **Load all (posture)** + **Submit all (CC-BY)** without changing the dataset API contract.
- Opt-in Celery beat: daily merge+eval pipeline; per-minute harvest + scaffold refresh.
- Admin **Ops** tab for Auto-Scale / Auto-Train / Learning Tick with runtime overrides stored in `admin_store` (Redis), effective helpers used by beat tasks.
- All schedulers **off by default**; env flags remain the defer path.

## Non-goals

- Full per-user workspace isolation of missions/results beyond existing `org_id` tenancy.
- Literal GPU QLoRA every minute (or every day without an explicit GPU flag).
- Scraping external exploit corpora or criminal PoC training data.
- Replacing Auth0 / OIDC; sessions wrap the same `session["user"|"role"|"org_id"]` contract.

---

## Architecture

```
┌─────────────┐     cookie (session id)     ┌──────────────────┐
│  SPA / Auth │ ───────────────────────────►│ Flask dashboard  │
└─────────────┘                             │ Flask-Session    │
                                            │ → Redis sess:*   │
                                            └────────┬─────────┘
                                                     │
     Admin Ops UI ──PUT /api/admin/settings/ops──────┤
                                                     ▼
                                            ┌──────────────────┐
                                            │ admin_store      │
                                            │ auto_scale       │
                                            │ auto_train       │
                                            │ learning_tick    │
                                            └────────┬─────────┘
                                                     │ effective_*()
                    ┌────────────────────────────────┼────────────────┐
                    ▼                                ▼                ▼
           Celery Beat                      scale_workers_tick   learning_tick
           (always register cheap          (every 30s if on)    (every 60s if on)
            wrappers that no-op)           daily_ml_pipeline
                                           (crontab if on)
```

Effective flag resolution (same order as RBAC):

1. `admin_store` override if not `null`
2. else environment variable
3. else `false`

---

## 1. Per-user Redis sessions

### Behavior

- Add `Flask-Session` dependency.
- In `dashboard.py` after `SECRET_KEY` is set:
  - Prefer Redis session interface when `flask_session` + Redis are available.
  - `SESSION_TYPE=redis`, `SESSION_REDIS` = shared Redis client / URL (same construction as Celery `REDIS_URL`).
  - Key prefix `cerberus:sess:`.
  - `SESSION_USE_SIGNER=True`, `SESSION_PERMANENT=False` (or short lifetime via `PERMANENT_SESSION_LIFETIME`, default 12h).
  - Cookie: `HttpOnly`, `SameSite=Lax`, `Secure` when `CERBERUS_SESSION_SECURE` is true (or when request is HTTPS / `PREFERRED_URL_SCHEME=https`).
- If Flask-Session or Redis is unavailable: keep today’s cookie sessions and log a warning (dev/lab fallback).
- When `SECRET_KEY` is still the hardcoded default `cerberus-x-secret`, log a warning on startup. When `rbac_enforce` is effective, surface `secret_key_insecure: true` on `GET /api/admin/settings` so Admin can see the misconfiguration; do not crash the process.

### Unchanged

- `security/rbac.py`, Auth0 sync, `/auth/*` still read/write Flask `session` keys. No API contract change for `/api/rbac/me`.

### Files

- `requirements.txt` — `Flask-Session`
- `src/orchestrator/dashboard.py` — session init helper
- `.env.example` — `CERBERUS_SESSION_SECURE`, note on `SECRET_KEY`

---

## 2. Load all / Submit all examples (frontend)

### Behavior

In `FirebreakPanel` Dataset contribute section:

1. Keep posture select + single-example listbox.
2. Add **Load all (posture)** — stages every example currently in `examples` (already fetched for the selected posture / “all”) into a checklist preview; all checked by default.
3. Add **Submit all (CC-BY)** — for each checked row, call existing `contributeDataset` sequentially (or small concurrency ≤3); show `saved/total` and per-row errors; skip empty prompt/response.
4. Single-row load into the textareas remains unchanged.

### API

No backend change. Reuse:

- `GET /api/dataset/examples?posture=&limit=`
- `POST /api/dataset/contribute`

### Files

- `frontend/src/components/FirebreakPanel.tsx`
- Optional small helper in `frontend/src/api/client.ts` if batch helper improves tests
- Vitest coverage for load-all staging and submit-all call count

---

## 3. Daily ML pipeline

### Behavior

Module `orchestrator/ml/auto_train.py`:

- `run_daily_pipeline()`:
  1. Merge contributions JSONL + posture seeds (reuse existing merge scripts / pipeline helpers where possible).
  2. Run planner schema eval + security QA eval (dry-run safe).
  3. Write report under `output/ml/daily_report.json` (plus a short `.md` sibling) and `audit_log("AUTO_TRAIN_DAILY", …)`.
  4. QLoRA: **dry-run only** unless `CERBERUS_TRAIN_GPU` is truthy; never block the beat worker on a multi-hour train without that flag.

### Scheduling

- Celery task `orchestrator.ml.daily_pipeline` registered from `celery_app.py`.
- Crontab hour from `CERBERUS_AUTO_TRAIN_HOUR` (default `3` UTC).
- Task body **first line**: if not `effective_auto_train()`, return `{"skipped": true}` (so Admin Off stops work without worker restart).
- Beat may always register the periodic entry; the effective check is the gate.

### Env / Admin

- Env: `CERBERUS_AUTO_TRAIN`, `CERBERUS_AUTO_TRAIN_HOUR`, `CERBERUS_TRAIN_GPU`
- Admin override: `auto_train` in settings

---

## 4. Per-minute learning tick

### Behavior

Module `orchestrator/ml/harvest.py`:

- `learning_tick()`:
  1. Scan recent completed missions in `playbook_jobs` (SUCCESS / terminal states).
  2. For each not yet harvested (track ids in Redis set `cerberus:ml:harvested` or append-only marker), write a planner-shaped prompt→response pair to `output/dataset/harvest.jsonl` (PII redaction via `dataset.pipeline.redact_pii` / `normalize_record`).
  3. Call `scaffolds.health_all()` (or equivalent) to refresh latency EMA / health used by the router.
  4. Return counts; audit only on non-zero harvest or errors (avoid log spam).

### Scheduling

- `add_periodic_task(60.0, learning_tick.s(), …)` when beat configures.
- Task gates on `effective_learning_tick()`.

### Env / Admin

- Env: `CERBERUS_LEARNING_TICK`
- Admin override: `learning_tick`

---

## 5. Admin Ops tab + Auto-Scale override

### UI

New Admin tab **Ops** (`frontend/src/views/Admin.tsx`):

| Control | Values | Copy |
|---------|--------|------|
| Auto-Scale | On / Off / Defer to env | Celery beat scales workers every ~30s when on |
| Auto-Train (daily) | On / Off / Defer to env | Nightly merge + eval; GPU train only if `CERBERUS_TRAIN_GPU` |
| Learning Tick | On / Off / Defer to env | Every minute: harvest missions + refresh scaffolds |

Show **effective** state under each control (like RBAC).

### Backend

Extend `security/admin_store.py`:

- Settings keys: `auto_scale`, `auto_train`, `learning_tick` (`true` / `false` / omitted/`null` = defer).
- Helpers: `set_ops_flag(name, value)`, `auto_scale_override()`, `auto_train_override()`, `learning_tick_override()`.
- Public effective helpers (e.g. in `workers/scaling.py` or `orchestrator/ml/flags.py`):
  - `effective_auto_scale()`
  - `effective_auto_train()`
  - `effective_learning_tick()`

API:

- `PUT /api/admin/settings/ops` — body may include any of the three keys; `null` clears override.
- `GET /api/admin/settings` — include keys in `settings` and `effective`.
- Audit: `ADMIN_OPS_SET`.

### Auto-Scale wiring

- Replace raw `os.environ["CERBERUS_AUTO_SCALE"]` checks in `celery_app.py` scale tick with `effective_auto_scale()`.
- Register the scale periodic task always (or register always and no-op inside), so Admin On works without process restart; Off skips work inside the tick.
- One-shot `POST /api/scale/auto` remains available for manual scale regardless of the beat flag (document that; do not block one-shot behind the flag).

---

## Error handling

- Session Redis down → fall back to cookie sessions; log once per process.
- Daily pipeline / harvest exceptions → catch, audit with severity, return error payload; do not crash the worker.
- Submit-all: continue after individual contribute failures; surface failed ids in UI.
- Admin Ops PUT: validate keys; 400 on unknown flag names.

## Testing

| Area | Cases |
|------|--------|
| Sessions | Redis session config applied when available; fallback path; cookie flags |
| Ops flags | Override beats env; `null` defers; effective helpers |
| Beat gates | Tick returns skipped when Off |
| Harvest | Completed fake job → one JSONL row; duplicate id not re-harvested |
| Daily pipeline | Dry-run returns report dict without GPU |
| Frontend | Load all stages N rows; Submit all calls contribute N times |
| Admin Ops | Tab renders three controls; PUT updates settings |

## Rollout

1. Ship code with all flags default Off / defer.
2. Document Ops tab + env vars in `docs/user_manual.md` / `.env.example`.
3. Operators enable via Admin or env after Redis + Celery beat are running.

## Success criteria

- Two browsers / two users get distinct Redis session keys; logout clears that user’s server session.
- Operator can load and submit all aggressive (or defensive / balanced) ready-made examples in one flow.
- With Learning Tick On, a finished mission appears in harvest JSONL within ~1–2 minutes.
- With Auto-Train On, a dry-run report appears after the scheduled hour (or manual task invoke in tests).
- Admin can turn Auto-Scale On without redeploying; Off stops further scale ticks.
