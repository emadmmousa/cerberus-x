# Proxy Settings UI Design

## Goal

Let operators paste or edit Oxylabs proxy URL/credentials from Mission Control, persist them for workers without a restart, and also overwrite local `.env` plus the Kubernetes Secret so Compose and cluster bootstrap stay in sync.

This **extends** `2026-07-19-oxylabs-proxy-react-console-design.md`. That doc forbade accepting credentials in the UI; this design deliberately supersedes that boundary for a local/operator-controlled console: the browser may send credentials to the orchestrator over the existing localhost-facing dashboard, but GET responses and logs must never return the plaintext password.

## Decisions (approved)

| Topic | Choice |
| --- | --- |
| Persistence for live runs | Redis key shared by orchestrator + workers |
| Bootstrap / file sync | Overwrite `OXYLABS_PROXY_*` in configured `.env` on every save |
| Cluster sync | Patch K8s Secret (user/pass) + ConfigMap (host/port/protocol) when in-cluster |
| Input UX | Full proxy URL paste **and** discrete editable fields |
| Password on reload | Masked (`••••••••`); never reveal; omit on save to keep existing |
| Credential source priority | Redis → env → none |

## Architecture

```text
Browser (Proxy Settings panel)
  -> PUT /api/proxy/settings  (credentials in body, TLS/local only)
  -> Orchestrator:
       1. Write Redis cerberus:proxy:settings
       2. Upsert OXYLABS_PROXY_* in CERBERUS_ENV_FILE
       3. Patch K8s Secret + ConfigMap (best-effort)
  -> Workers read Redis first, else env, when building upstream URL
  -> Local forwarder still isolates secrets from tool argv
```

### Source of truth

| Layer | Role |
| --- | --- |
| Redis `cerberus:proxy:settings` | Live source for new scans (no restart) |
| `.env` (`CERBERUS_ENV_FILE`) | Persist for Compose / local reboot |
| K8s Secret + ConfigMap | Persist credentials (Secret) and host/port/protocol (ConfigMap) for new pods |
| Process env | Fallback when Redis empty |

Stored Redis JSON:

```json
{
  "username": "customer-…",
  "password": "…",
  "host": "pr.oxylabs.io",
  "port": 7777,
  "protocol": "http"
}
```

Allowed protocols: `http`, `https`, `socks5h` (same as existing proxy config).

### Boundaries

- Celery task payloads still carry only `use_proxy` / `proxy_protocol` — never credentials.
- Tool argv / subprocess env still use credential-free localhost forwarder URLs.
- GET APIs never return plaintext password; may return `password_set` and redacted URL.
- Logs use `redact_proxy_url` before emit.
- Clear Redis (`DELETE`) returns to env-only; default clear does **not** wipe `.env` or K8s unless `?purge=true`.

## Backend

### Credential resolution

Update `proxy_config` (and local forwarder upstream builders) so:

1. If Redis settings exist and have username+password → use them.
2. Else if `OXYLABS_PROXY_USERNAME` + `OXYLABS_PROXY_PASSWORD` env → use them.
3. Else → not configured.

`credentials_configured()` and `/api/proxy/status` must reflect Redis **or** env.

### API

#### `GET /api/proxy/settings`

```json
{
  "configured": true,
  "source": "redis" | "env" | "none",
  "username": "customer-…",
  "password_set": true,
  "host": "pr.oxylabs.io",
  "port": 7777,
  "protocol": "http",
  "proxy_url_redacted": "http://customer-…:***@pr.oxylabs.io:7777"
}
```

#### `PUT /api/proxy/settings`

Accept either or both:

- `{ "proxy_url": "http://user:pass@host:port" }`
- `{ "username", "password", "host", "port", "protocol" }`

Rules:

- Parse URL to fill fields; discrete fields win on conflict.
- Empty/omitted `password` when `password_set` already true → keep existing password.
- Missing required host/username (or unparseable URL) → `400`, no writes.
- On success, apply in order:
  1. Redis write (required). Failure → `503`, do not touch `.env` or K8s.
  2. Upsert `.env` keys: `OXYLABS_PROXY_USERNAME`, `OXYLABS_PROXY_PASSWORD`, `OXYLABS_PROXY_HOST`, `OXYLABS_PROXY_PORT`, `OXYLABS_PROXY_PROTOCOL`. Path from `CERBERUS_ENV_FILE` (default `/app/.env`).
  3. In-cluster best-effort sync:
     - Patch Secret `cerberus-secrets`: `OXYLABS_PROXY_USERNAME`, `OXYLABS_PROXY_PASSWORD`
     - Patch ConfigMap `cerberus-config`: `OXYLABS_PROXY_HOST`, `OXYLABS_PROXY_PORT`, `OXYLABS_PROXY_PROTOCOL`
     Live workers already prefer Redis; ConfigMap/Secret keep new pods aligned.

Response shape:

```json
{
  "ok": true,
  "configured": true,
  "source": "redis",
  "username": "…",
  "password_set": true,
  "host": "…",
  "port": 7777,
  "protocol": "http",
  "proxy_url_redacted": "…",
  "redis": { "ok": true },
  "env": { "ok": true } | { "ok": false, "error": "…" },
  "k8s": { "ok": true } | { "ok": false, "error": "…" }
}
```

HTTP `200` when Redis succeeded even if env/k8s failed; UI surfaces partial success.

#### `DELETE /api/proxy/settings`

Delete Redis key. With `?purge=true`, also clear the five `OXYLABS_PROXY_*` values in `.env` and remove/blank Secret keys (best-effort).

#### `GET /api/proxy/status`

Keep `{ "configured": bool }` for the existing badge; `configured` true if Redis or env has credentials.

### `.env` upsert

- Preserve unrelated keys and comments where practical.
- Replace existing `OXYLABS_PROXY_*` lines or append if missing.
- Never write secrets into git-tracked files; only the configured env file path.
- Compose: mount repo `.env` into orchestrator at `/app/.env` and set `CERBERUS_ENV_FILE=/app/.env`.

### Kubernetes

- Orchestrator ServiceAccount + Role/RoleBinding in namespace `cerberus-x` limited to:
  - Secret `cerberus-secrets`: `get`, `patch`
  - ConfigMap `cerberus-config`: `get`, `patch`
- Detect in-cluster via service account token / `KUBERNETES_SERVICE_HOST`.
- Outside cluster: `k8s.ok=false` with a short “not in cluster” message — not a hard failure.
- Patching Secret/ConfigMap updates bootstrap for **new** pods; live workers already use Redis, so no forced restart required for new scans.

## Frontend

Extend the existing **Proxy Routing** panel (`ProxyToggle`):

- Collapsible **Proxy Settings** section.
- Full proxy URL field + **Parse URL**.
- Discrete fields: protocol, host, port, username, password.
- On load: populate from `GET /api/proxy/settings`; password field shows a fixed mask when `password_set`, never the real value, no reveal toggle.
- **Save credentials** → `PUT`; show per-target status (`redis` / `env` / `k8s`).
- Badge refreshes to configured after successful Redis write.
- Existing per-run enable toggle + protocol for the run remain unchanged.
- Do not store credentials in `localStorage` / `sessionStorage`.

## Error handling

| Case | Behavior |
| --- | --- |
| Bad URL / missing fields | `400`; no side effects |
| Redis down | `503`; no `.env` / K8s writes |
| `.env` unwritable | `200` + `env.ok=false`; runtime still updated |
| K8s missing/forbidden | `200` + `k8s.ok=false` |
| Password in errors/logs | Forbidden — redact |

## Testing

- Backend: URL parse; PUT → Redis; GET redacts; empty password keeps existing; `.env` upsert helper; K8s client mocked.
- Frontend: parse fills fields; save calls PUT; mask behavior; badge update.
- Regression: existing `/api/run` proxy toggle tests and `proxy_config` tool resolution tests remain green.

## Out of scope

- Rotating Oxylabs account in their dashboard.
- Restarting worker pods after Secret patch (Redis covers live path).
- Authn/authz on the dashboard itself (still localhost / cluster-internal trust model).
- SOCKS upstream forwarder rewrite beyond existing protocol support.
