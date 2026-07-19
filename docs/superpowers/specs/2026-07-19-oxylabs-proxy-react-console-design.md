# Oxylabs Proxy Routing + React Operator Console Design

## Goal

Add optional, per-run Oxylabs proxy routing for authorized injection and brute-force (and other compatible) scanners, and replace the Flask Jinja dashboard with a React + Vite operator console using a dark tactical visual system. Proxy credentials must never appear in git, playbooks, Celery payloads, tool argv, the browser, or unredacted logs.

## Decisions (approved)

| Topic | Choice |
| --- | --- |
| Proxy activation | Per-run toggle, default off |
| Tool scope | Every outbound scanner that can safely use a proxy |
| Unsupported tools | Best-effort: run direct + structured `proxy_skipped` note |
| Default protocol | HTTP |
| Architecture | Worker local credential-isolating forwarder + React SPA |
| UI scope | Full replacement of current dashboard |
| Visual direction | Dark tactical ops console |

## Architecture

Workers hold Oxylabs secrets via environment / Kubernetes Secret. When a run sets `use_proxy=true`, Celery tasks receive only `use_proxy` and `proxy_protocol` (default `http`). A local forwarder on the worker authenticates upstream to Oxylabs; tools receive a credential-free localhost proxy URL (or equivalent env). Unsupported tool/protocol combinations run directly and record `proxy_skipped`.

The React SPA is built with Vite and served as static assets by Flask. Existing REST and Socket.IO contracts are preserved and extended; the browser never receives or stores Oxylabs credentials.

```text
Browser (React SPA)
  -> Flask /api/run { target, use_proxy, proxy_protocol }
  -> Celery kwargs { use_proxy, proxy_protocol }   # no secrets
  -> Worker + local forwarder (secrets from env)
  -> Tool flags/env -> 127.0.0.1 forwarder -> Oxylabs -> target
```

### Boundaries

- Secrets: worker (+ forwarder) only.
- Orchestrator: may know enablement flags; must not require Oxylabs password.
- UI: never accepts Oxylabs username/password; shows “worker-configured” status only.
- Logs/errors: redact userinfo from any proxy URL before emit.

## Backend

### Environment variables

Document in `.env.example` with blank credentials:

- `OXYLABS_PROXY_HOST` (default `pr.oxylabs.io`)
- `OXYLABS_PROXY_PORT` (default `7777`)
- `OXYLABS_PROXY_USERNAME`
- `OXYLABS_PROXY_PASSWORD`
- `OXYLABS_PROXY_PROTOCOL` (default `http`; allowed: `http`, `https`, `socks5h`)
- `CERBERUS_LOCAL_PROXY_HOST` (default `127.0.0.1`)
- `CERBERUS_LOCAL_PROXY_PORT` (default `18080`)

Compose already loads `.env` into workers. Kubernetes: host/port/protocol in ConfigMap; username/password via `secretKeyRef` on the **worker** deployment only. Helm must use `existingSecret` for credentials (no plaintext values in `values.yaml`).

**Ops note:** Credentials pasted into chat are considered exposed. Rotate the Oxylabs password before production use. Do not commit real credentials into `k8s/secrets.yaml`.

### `src/tools/proxy_config.py`

Responsibilities:

- Parse enablement from task kwargs + env availability.
- URL-encode credentials when building the upstream URL for the forwarder only.
- `resolve_for_tool(tool: str, *, use_proxy: bool, protocol: str = "http")` returns:

```python
{
  "mode": "local_proxy" | "direct" | "unsupported",
  "flags": list[str],          # argv additions without secrets
  "env": dict[str, str],       # subprocess env overlays without secrets
  "note": str | None,          # e.g. proxy_skipped reason
  "local_proxy_url": str | None,
}
```

- Provide `redact_proxy_url(url: str) -> str` for logging.

### Local credential-isolating forwarder

- Runs on each worker (in-process thread/process or sidecar).
- Listens on `CERBERUS_LOCAL_PROXY_HOST:CERBERUS_LOCAL_PROXY_PORT`.
- Upstream target: Oxylabs endpoint using protocol from env / per-run override.
- Injects Basic auth toward Oxylabs; tools talk to localhost without credentials.
- Health check required before proxied tool execution; failure returns a clear error without leaking secrets.
- HTTP is the first-class path (default). HTTPS and SOCKS5h may be offered in UI/API; if the forwarder does not yet support a protocol, treat as `unsupported` / best-effort per tool matrix rather than inventing silent fallbacks.

### Tool wiring (best-effort)

Apply local proxy flags/env where supported; otherwise `mode=unsupported` → run direct + `proxy_skipped`:

| Tool | Preferred injection |
| --- | --- |
| sqlmap | `--proxy` → local HTTP URL (no `--proxy-cred`) |
| hydra | `HYDRA_PROXY_HTTP` / `HYDRA_PROXY` env to local endpoint |
| gobuster | `--proxy` local URL; preflight `urlopen` must inherit proxy env |
| ffuf | `-x` local URL |
| nikto | `-useproxy` / config pointing at local HTTP |
| nuclei | `-proxy` local URL where supported |
| whatweb | `--proxy` host:port of local forwarder (no user:pass) |
| xsstrike | prefer env (`HTTP_PROXY`/`HTTPS_PROXY` to local) over brittle `--proxy` boolean |

Result metadata should include `proxy: { enabled, protocol, mode, note }` (redacted).

### API / orchestration

Extend `POST /api/run` JSON body:

```json
{
  "target": "example.com",
  "use_proxy": false,
  "proxy_protocol": "http"
}
```

- `use_proxy` defaults to `false`.
- `proxy_protocol` defaults to `http`; allowed values: `http`, `https`, `socks5h`.
- Pass only these fields into playbook job state and Celery kwargs.
- CLI may gain matching flags later; not required for the first cut if dashboard is primary.

### Explicitly out of scope (this design)

- Enforcing playbook `when` / `depends_on` via `DecisionEngine` (known gap; separate follow-up).
- Shared Socket.IO / multi-replica orchestrator state (document single-replica or sticky sessions until fixed).
- Live Oxylabs integration tests in CI.

## Frontend

### Stack

- New app under `frontend/` (Vite + React + TypeScript).
- Production build emitted to a path Flask serves as static assets (e.g. `src/orchestrator/static/app/` or `frontend/dist` copied in Docker).
- Flask serves SPA `index.html` for `/` and client routes; keeps `/api/*`, `/status/<task_id>`, `/results`, `/metrics`, `/health`, `/ready`, and Socket.IO.
- Orchestrator Dockerfile gains a Node build stage.
- Preserve text-safe result rendering (no `innerHTML` for untrusted payloads).

### Visual system

- Dark tactical ops console: near-black canvas, cyan / amber / red status language, sharp geometry.
- Brand “CERBERUS-X” as a hero-level signal on the mission launch surface.
- Expressive typography (not Inter/Roboto/Arial/system defaults).
- Atmospheric background (subtle grid / noise / gradient layers)—not flat single-color.
- Avoid purple-on-white, cream+terracotta, and broadsheet newspaper layouts.
- Intentional motion (2–3 presence cues): launch confirm, status pulse, log stream entrance.

### Views (full replacement of current dashboard)

1. **Mission Launch** — target, proxy toggle, protocol select, run, task ID, live phase status.
2. **Findings** — structured cards + raw JSON drawer.
3. **Exploit Ops** — Metasploit module search/load/run, jobs, sessions.
4. **Console** — Socket.IO MSF console with streaming buffer.
5. **Event Log** — Socket.IO `log` feed with filters (level / tool / `proxy_skipped`).

### Interaction rules

- After run: poll `/status/<task_id>`; refresh findings for active target.
- Confirm destructive actions (stop job, close session).
- Proxy UI never collects Oxylabs credentials; show worker-config status if a future `/api/proxy/status` endpoint is added (optional; may infer from env presence server-side without exposing secrets).
- No default real-world target domain in the form.

## Testing

### Backend

- `proxy_config`: disabled by default; default protocol `http`; redaction; encoding; per-tool modes.
- Wrappers: when enabled, receive local proxy flags/env; gobuster preflight inherits proxy env; unsupported → direct + `proxy_skipped`.
- API: accepts `use_proxy` / `proxy_protocol`; Celery kwargs contain no credentials.
- Forwarder: health failure is safe; no secret leakage in exceptions.

### Frontend

- Mission Launch wires toggle/protocol into `POST /api/run`.
- Findings render text-safe content.
- Contract alignment with existing Metasploit REST + Socket.IO event names.

### Regression

- Existing orchestrator / wrapper / API tests remain green.
- Docker build asserts frontend `dist` (or static app) is present in the orchestrator image.

### Success criteria

1. Toggle off → tool invocation unchanged.
2. Toggle on + HTTP → supported tools use local forwarder; others run direct with logged skip.
3. UI never handles Oxylabs password.
4. React console fully replaces the operator workflows previously in `templates/index.html`.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Credentials in argv / Celery JSON | Local forwarder; kwargs are flags only |
| Tool protocol quirks | Best-effort matrix + `proxy_skipped` |
| Oxylabs port restrictions (e.g. SSH/22) | Document; Hydra SSH may skip or fail upstream |
| Multi-worker Flask in-memory state | Single replica / sticky sessions until shared state |
| Frontend build complexity | Multi-stage Docker; CI build step |

## Implementation order

1. `proxy_config` + tests + wrapper hooks (proxy off by default).
2. Local forwarder + worker env / K8s Secret wiring (blank secrets in examples).
3. Extend `POST /api/run` and task kwargs.
4. Scaffold React app; Mission Launch + Event Log against live APIs.
5. Port Findings, Exploit Ops, Console; remove dependency on Jinja dashboard.
6. Docker/K8s image + static serving; verify port-forward UX.
