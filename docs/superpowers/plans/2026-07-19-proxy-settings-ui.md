# Proxy Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators save Oxylabs proxy URL/credentials from Mission Control into Redis (live), `.env` (Compose), and K8s Secret/ConfigMap (bootstrap).

**Architecture:** New `proxy_settings` module owns Redis CRUD + URL parse + redacted public view. `proxy_config` / local forwarder resolve credentials Redis→env. Dashboard exposes GET/PUT/DELETE. UI extends `ProxyToggle`. K8s sync uses in-cluster REST (no new deps).

**Tech Stack:** Python/Flask, redis 5.x, React/Vite, Vitest, Pytest, Kubernetes RBAC manifests

## Global Constraints

- Never return plaintext password from GET APIs or logs.
- Celery payloads stay credential-free (`use_proxy` / `proxy_protocol` only).
- Redis write is required for PUT success; `.env` and K8s are best-effort.
- Empty password on PUT keeps existing password when one is already set.
- Allowed protocols: `http`, `https`, `socks5h`.
- No new Python dependencies (use `redis` + `requests` already present).

## File map

| File | Responsibility |
| --- | --- |
| `src/tools/proxy_settings.py` | Parse URL, Redis get/set/delete, public redacted view, `load_credentials()` |
| `src/tools/env_file.py` | Upsert/clear `OXYLABS_PROXY_*` lines in `.env` |
| `src/tools/k8s_proxy_sync.py` | Best-effort patch Secret + ConfigMap via in-cluster API |
| `src/tools/proxy_config.py` | Use `load_credentials()` for configured/upstream |
| `src/tools/local_proxy.py` | Auth header from `load_credentials()` |
| `src/tools/wrappers/_proxy.py` | Preflight from `load_credentials()` |
| `src/orchestrator/dashboard.py` | `/api/proxy/settings` GET/PUT/DELETE; status uses Redis|env |
| `frontend/src/components/ProxyToggle.tsx` | Settings form UI |
| `frontend/src/api/client.ts` | API client helpers |
| `docker-compose.yml` | Mount `.env` + `CERBERUS_ENV_FILE` |
| `k8s/orchestrator-rbac.yaml` | SA + Role + RoleBinding |
| `k8s/orchestrator-deployment.yaml` | serviceAccountName |

---

### Task 1: proxy_settings store + URL parse

**Files:**
- Create: `src/tools/proxy_settings.py`
- Test: `tests/test_proxy_settings.py`

**Interfaces:**
- Produces:
  - `REDIS_KEY = "cerberus:proxy:settings"`
  - `parse_proxy_url(url: str) -> dict`
  - `save_settings(data: dict) -> None`
  - `load_settings() -> dict | None`
  - `clear_settings() -> None`
  - `load_credentials() -> dict | None`  # Redis then env; keys username/password/host/port/protocol
  - `public_view(creds: dict | None, *, source: str) -> dict`
  - `merge_put_body(body: dict, existing: dict | None) -> dict`  # raises ValueError

- [ ] **Step 1: Write failing tests** for parse, merge (empty password keeps existing), public_view redaction, save/load via fakeredis-like monkeypatch.

- [ ] **Step 2: Implement module** using `redis.from_url` from `orchestrator.celeryconfig.REDIS_URL` (lazy import to avoid cycles). Support `CERBERUS_PROXY_SETTINGS_BACKEND=memory` for tests.

- [ ] **Step 3: Pytest green; commit**

```bash
pytest tests/test_proxy_settings.py -v
git add src/tools/proxy_settings.py tests/test_proxy_settings.py
git commit -m "feat(proxy): add redis-backed proxy settings store"
```

---

### Task 2: `.env` upsert helper

**Files:**
- Create: `src/tools/env_file.py`
- Test: `tests/test_env_file.py`

**Interfaces:**
- Produces: `upsert_oxylabs_keys(path: str, values: dict[str, str]) -> None`
- Produces: `clear_oxylabs_keys(path: str) -> None`

Keys: `OXYLABS_PROXY_USERNAME`, `OXYLABS_PROXY_PASSWORD`, `OXYLABS_PROXY_HOST`, `OXYLABS_PROXY_PORT`, `OXYLABS_PROXY_PROTOCOL`.

- [ ] **Step 1: Failing tests** — replace existing lines, append missing, preserve other keys/comments, clear blanks values.

- [ ] **Step 2: Implement; pytest green; commit**

```bash
git commit -m "feat(proxy): upsert oxylabs keys in env file"
```

---

### Task 3: Wire credential resolution into proxy_config + forwarder

**Files:**
- Modify: `src/tools/proxy_config.py`
- Modify: `src/tools/local_proxy.py` (`_proxy_authorization_header`)
- Modify: `src/tools/wrappers/_proxy.py` (`_preflight_upstream_note`)
- Test: `tests/test_proxy_config.py` (extend)

**Interfaces:**
- Consumes: `load_credentials()`
- Produces: `credentials_configured()` / `upstream_proxy_url()` use Redis-first credentials

- [ ] **Step 1: Failing test** — with Redis settings and empty env, `credentials_configured()` is True and upstream uses Redis user.

- [ ] **Step 2: Implement; pytest green; commit**

```bash
git commit -m "feat(proxy): resolve credentials from redis then env"
```

---

### Task 4: Dashboard API + K8s sync stub

**Files:**
- Create: `src/tools/k8s_proxy_sync.py`
- Modify: `src/orchestrator/dashboard.py`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_k8s_proxy_sync.py`

**Interfaces:**
- Produces: `sync_proxy_to_kubernetes(creds: dict) -> dict` → `{ok: bool, error?: str}`
- Routes: `GET/PUT/DELETE /api/proxy/settings` as in spec
- `GET /api/proxy/status` uses `load_credentials() is not None` (or flagged env)

K8s sync: if `KUBERNETES_SERVICE_HOST` unset → `{ok: false, error: "not in cluster"}`. Else PATCH Secret/ConfigMap with SA token + `requests` (base64 for Secret data).

- [ ] **Step 1: Failing API tests** — PUT writes Redis, GET redacts, empty password keeps, Redis failure → 503, env failure still 200 with `env.ok=false`.

- [ ] **Step 2: Implement routes + k8s helper; pytest green; commit**

```bash
git commit -m "feat(proxy): add proxy settings API with env and k8s sync"
```

---

### Task 5: Frontend Proxy Settings UI

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/ProxyToggle.tsx`
- Modify: `frontend/src/styles/global.css` (minimal form layout if needed)
- Test: `frontend/src/__tests__/MissionControl.test.tsx` (mock `/api/proxy/settings`)
- Optional: `frontend/src/__tests__/ProxyToggle.test.tsx`

**Interfaces:**
- Produces: `getProxySettings()`, `putProxySettings(body)`, `deleteProxySettings(purge?)`
- UI: URL + Parse, discrete fields, masked password, Save, status lines for redis/env/k8s

- [ ] **Step 1: Failing frontend test** for parse + save PUT body.

- [ ] **Step 2: Implement UI; vitest green; build SPA into static if project expects it; commit**

```bash
cd frontend && npm test -- --run
git commit -m "feat(ui): add proxy credentials settings panel"
```

---

### Task 6: Deploy wiring (Compose + K8s RBAC)

**Files:**
- Modify: `docker-compose.yml` (orchestrator volumes + `CERBERUS_ENV_FILE=/app/.env`)
- Create: `k8s/orchestrator-rbac.yaml`
- Modify: `k8s/orchestrator-deployment.yaml` (`serviceAccountName: orchestrator`)
- Modify: `.env.example` note that UI can overwrite Oxylabs keys

- [ ] **Step 1: Apply manifests content; no secrets in git**

- [ ] **Step 2: Commit**

```bash
git commit -m "chore(deploy): mount env file and grant orchestrator proxy sync rbac"
```

---

### Task 7: Regression suite

- [ ] Run: `pytest tests/test_proxy_settings.py tests/test_env_file.py tests/test_proxy_config.py tests/test_dashboard_api.py tests/test_k8s_proxy_sync.py -v`
- [ ] Run: `cd frontend && npm test -- --run`
- [ ] Fix any breakages; final commit if needed
