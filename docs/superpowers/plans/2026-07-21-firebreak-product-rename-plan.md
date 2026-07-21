# Firebreak Product Rename — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-cutover rename of the entire product from Cerberus-X to Firebreak, with AI Lab at `/ai-lab`, domains centered on `firebreak.com`, and zero tracked Cerberus identifiers remaining.

**Architecture:** Dependency-ordered mechanical rename: core libraries (env/Redis/headers/metrics) first, then APIs/model, frontend (rebuild static), deploy manifests, docs/CI scan. No dual-read aliases. Python import paths (`orchestrator`, `security`, `tools`) stay.

**Tech Stack:** Flask, React/Vite, Celery, Redis, Docker Compose, Helm, pytest, vitest

**Spec:** `docs/superpowers/specs/2026-07-21-firebreak-product-rename-design.md`

## Global Constraints

- Hard cutover: no `CERBERUS_*` fallbacks.
- Canonical site: `https://firebreak.com`; app: `https://app.firebreak.com`.
- Redirects: `firebreak.net` / `.org` / `.info` → `https://firebreak.com` (docs + runbook).
- AI feature: **AI Lab**, route `/ai-lab`, API `/api/ai-lab/status`.
- Model id: `firebreak`; scaffold: `ollama-primary`.
- Env: `CERBERUS_*` → `FIREBREAK_*`; Redis `cerberus:` → `firebreak:`; headers `X-Cerberus-*` → `X-Firebreak-*`.
- npm: `firebreak-console`; images: `emadmmousa/firebreak-*`; Helm chart/dir: `firebreak`.
- Rebuild Vite static assets; do not hand-edit hashed bundles.
- Forbidden-name scan must pass on tracked sources.
- Conventional Commits; minimize unrelated WIP in rename commits.

## File map (high level)

| Area | Primary paths |
|------|----------------|
| Env / session / Redis / RBAC | `.env.example`, `session_config.py`, `admin_store.py`, `job_store.py`, `rbac.py`, `mcp/sessions.py`, `prometheus_metrics.py`, `audit.py`, `elasticsearch_client.py` |
| AI Lab API | `api/scaffolds.py`, frontend routes/views/components/client |
| Model | `docker/ollama/Modelfile`, `scaffold_client.py`, `marketplace.py`, `prompts.py`, training scripts/seeds |
| Frontend brand | `frontend/index.html`, `AppShell.tsx`, `Login.tsx`, `package.json`, static rebuild |
| Deploy | `docker-compose.yml`, `docker/docker-compose.yml`, `helm/cerberus` → `helm/firebreak`, `k8s/*` |
| Docs / CI | README, manuals, `docs/RENAME_CUTOVER.md`, CI forbidden-name job |

---

### Task 1: Core identifiers (env, Redis, headers, metrics, secrets)

**Files:** All Python modules reading `CERBERUS_*` / `cerberus:` / `X-Cerberus-*` / `cerberus_*` metrics; `.env.example`; `session_config.py` insecure defaults.

- [ ] **Step 1:** Write/extend a small test asserting `FIREBREAK_*` env resolution and insecure secret `firebreak-secret` / `change-me`.
- [ ] **Step 2:** RED then GREEN — replace env prefixes, Redis prefixes, header names, claim keys, metric names, default secrets across `src/` and `.env.example`.
- [ ] **Step 3:** Run focused pytest for session/ops/rbac/metrics.
- [ ] **Step 4:** Commit `refactor: rename core env redis headers and metrics to firebreak`

---

### Task 2: Backend AI Lab API + model + MCP + prompts

**Files:** `api/scaffolds.py` (route rename), MCP blueprint name, Modelfile, scaffold client defaults, marketplace, prompts, control_plane UA, training scripts/seeds as needed for compile/tests.

- [ ] **Step 1:** Update tests for `/api/ai-lab/status`, model `firebreak`, MCP name `firebreak`.
- [ ] **Step 2:** Implement renames; keep Python packages unchanged.
- [ ] **Step 3:** pytest green for firebreak/ai-lab/mcp/scaffold tests.
- [ ] **Step 4:** Commit `refactor: rename ai lab api model and mcp identity`

---

### Task 3: Frontend brand + AI Lab route + static rebuild

**Files:** `frontend/src/**`, `frontend/index.html`, `frontend/package.json`, rename `Firebreak*` → `AiLab*`, rebuild `src/orchestrator/static/app`.

- [ ] **Step 1:** Update vitest for Firebreak brand + `/ai-lab`.
- [ ] **Step 2:** Rename components/routes/client helpers; replace visible copy.
- [ ] **Step 3:** `cd frontend && npm run build` into orchestrator static.
- [ ] **Step 4:** Commit `refactor(ui): rebrand to firebreak and move ai lab to /ai-lab`

---

### Task 4: Docker Compose + Helm + K8s

**Files:** compose files, `helm/cerberus` → `helm/firebreak` (git mv), Chart.yaml, values, templates, `k8s/*`, deploy scripts, Dockerfiles user/image names.

- [ ] **Step 1:** Rename containers/images/env in compose.
- [ ] **Step 2:** `git mv helm/cerberus helm/firebreak`; update chart name, helpers, namespace examples.
- [ ] **Step 3:** Update k8s manifests and deploy scripts.
- [ ] **Step 4:** Commit `refactor(deploy): rename compose helm and k8s to firebreak`

---

### Task 5: Docs, cutover runbook, forbidden-name CI

**Files:** README, user/developer/api docs, ROADMAP, CONTRIBUTING, SECURITY, training cards, `docs/RENAME_CUTOVER.md`, `.github/workflows/ci.yml` scan.

- [ ] **Step 1:** Add `docs/RENAME_CUTOVER.md` with domain/DNS/Auth0/Helm/Redis flush checklist.
- [ ] **Step 2:** Sweep docs for Firebreak branding and domains.
- [ ] **Step 3:** Add CI step: fail if tracked sources match Cerberus tokens (exclude `.git`, `node_modules`, `.venv`, maybe historical plan filenames only if body already updated — prefer zero matches including bodies).
- [ ] **Step 4:** Commit `docs: cutover runbook and firebreak branding sweep`

---

### Task 6: Final verification + leftover sweep

- [ ] **Step 1:** `rg` forbidden tokens on tracked files; fix stragglers (tests, seeds, comments, init scripts).
- [ ] **Step 2:** Run backend pytest batch + frontend vitest + confirm static build present.
- [ ] **Step 3:** Commit any fixes `fix: clear remaining cerberus identifiers`
- [ ] **Step 4:** Report remaining **external** steps (GitHub repo rename, DNS, image push) — do not claim those done unless executed with user approval.

## Spec coverage

| Spec item | Task |
|-----------|------|
| Env/Redis/headers/metrics | 1 |
| AI Lab routes/API/model | 2–3 |
| Frontend brand + rebuild | 3 |
| Compose/Helm/K8s | 4 |
| Domains + cutover docs | 5 |
| Forbidden scan | 5–6 |
| GitHub/DNS external | 6 (documented) |
