# Firebreak API Reference

Base URL (compose default): `http://localhost:5000`

Most mission endpoints do **not** require an API key. **MCP** requires `FIREBREAK_MCP_API_KEY` when set (Bearer or `X-API-Key`). Optional platform WAF/rate-limit middleware may apply to the orchestrator itself (`FIREBREAK_WAF_ENABLED`).

---

## Health & ops

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Readiness (SQLite / optional ES) |
| `GET` | `/metrics` | Basic metrics payload |
| `GET` | `/status/<task_id>` | Celery task status |
| `GET` | `/results` | Recent results (JSON) |

---

## Admin (RBAC admin role)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/settings` | Stored overrides, **effective** flags (`auto_scale`, `auto_train`, `learning_tick`, `rbac_enforce`, `edition`), `secret_key_insecure`, SSO readiness |
| `PUT` | `/api/admin/settings/ops` | Set ops automation overrides (see below) |
| `PUT` | `/api/admin/settings/rbac` | RBAC enforce override |
| `PUT` | `/api/admin/settings/edition` | Edition override (`community` / `pro`) |

### `PUT /api/admin/settings/ops`

Toggle background schedulers without redeploying. Body may include any of:

```json
{
  "auto_scale": true,
  "auto_train": false,
  "learning_tick": null
}
```

Each value is `true` (force ON), `false` (force OFF), or `null` (defer to env). Unknown keys return `400`. Effective resolution: Admin override → env (`FIREBREAK_AUTO_SCALE`, `FIREBREAK_AUTO_TRAIN`, `FIREBREAK_LEARNING_TICK`) → `false`.

Beat tasks always register but no-op when OFF. **`POST /api/scale/auto`** remains available for manual one-shot scale regardless of `auto_scale`.

---

## Missions

### `POST /api/run`

Start a playbook or AI mission.

```json
{
  "target": "https://lab.example",
  "evasion": "aggressive",
  "use_proxy": false,
  "proxy_protocol": "http",
  "ai_mode": false,
  "nl_goal": "",
  "confirm_high_risk": true
}
```

Default playbook is `playbooks/complete_dark_arsenal.yaml` (override with `?playbook=` or `PLAYBOOK_PATH`).
- `playbook` in the JSON body is ignored; use query `?playbook=playbooks/default.yaml` if needed.
- `evasion`: string (`off`/`low`/`medium`/`high`/`aggressive`) **or** full profile object from `evasion_profile()`.
- `ai_mode`: when true, uses planner loop instead of static phases only.

Response includes `job_id` for UI polling / Socket.IO.

### `GET /api/playbook`

List available playbooks and metadata.

### `GET /api/ai/sessions`

List AI session ids.

### `GET /api/ai/audit/<session_id>`

Audit trail for an AI session.

### `POST /api/ai/plan`

Dry-run / preview next AI phase for a target + goal (does not always enqueue).

---

## Active vulnerability scanner

### `POST /api/scan/start`

```json
{
  "target": "https://lab.example",
  "use_proxy": false,
  "proxy_protocol": "http",
  "evasion": {"level": "aggressive", "random_headers": true}
}
```

### `GET /api/scan/status/<job_id>`

Returns status + findings (SQLi, XSS, NoSQL, path traversal, open redirect, WAF/origin hints).

---

## Proxy (Oxylabs)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/proxy/status` | Whether proxy env is configured |
| `GET` | `/api/proxy/settings` | Current settings (secrets redacted) |
| `PUT` | `/api/proxy/settings` | Update settings |
| `DELETE` | `/api/proxy/settings` | Clear stored settings |
| `POST` | `/api/proxy/test` | Connectivity test |

---

## Aggressive / deception / scale

Prefix: `/api`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/aggressive/decide` | AI/heuristic follow-on suggestions |
| `POST` | `/api/aggressive/execute` | Execute aggressive playbook path |
| `POST` | `/api/playbook/dynamic` | Dynamic playbook with context |
| `POST` | `/api/deception/spawn` | Spawn honeypot helper |
| `POST` | `/api/deception/teardown` | Tear down honeypot |
| `POST` | `/api/scale/auto` | One-shot worker auto-scale hint (always available; not gated by Admin Auto-Scale) |
| `POST` | `/api/report/generate` | Generate session report |

---

## Metasploit RPC façade

Blueprint routes under the Metasploit API module (sessions, modules, execute). Prefer mission-driven `metasploit` tool tasks for normal engagements. Payload options (`PAYLOAD`, `LHOST`, `LPORT`) are filled by `tools.payload_strategy`.

---

## MCP (Model Context Protocol)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/mcp` | JSON-RPC tools (session, list_tools, run_tool, status, findings, …) |
| `GET` | `/mcp/sse` | Optional SSE transport |

Auth: `Authorization: Bearer <FIREBREAK_MCP_API_KEY>` or `X-API-Key`.

High-risk tools (`sqlmap`, `metasploit`, `hydra`, …) require `confirm: true` in the RPC args **only when** `FIREBREAK_AI_REQUIRE_CONFIRM=true` (default **false**).

---

## Auth (optional)

| Method | Path | Description |
|--------|------|-------------|
| `*` | `/auth/*` | Optional login helpers when enabled |
| `GET` | `/login` `/callback` `/logout` | Auth0 Regular Web App (when configured) |
| `GET` | `/api/oidc/status` | Auth0 / OIDC readiness + missing env names |

---

## Firebreak (AI / open-core)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/ai-lab/status` | Model, multi-scaffold, `cost_route`, edition, SSO, waves |
| `GET` | `/api/scaffolds` | Enabled scaffolds + health (`latency_ema_ms`, `cost_per_1k`) |
| `GET` | `/api/scaffolds/marketplace` | Builtin catalog (+ registered) |
| `POST` | `/api/scaffolds/marketplace` | Register live scaffold (**Pro**; requires `id`, `model`, `base_url`) |
| `DELETE` | `/api/scaffolds/marketplace/<id>` | Unregister a Pro marketplace scaffold |
| `GET` | `/api/blackboard/<mission_id>` | List Blackboard keys (org-scoped) |
| `GET`/`PUT` | `/api/blackboard/<mission_id>/<key>` | Read / write a Blackboard doc |
| `GET` | `/api/playbooks` | Playbook catalog (`?posture=` filters) |
| `GET` | `/api/missions/<id>/hardening` | Hardening recommendations (+ `?format=markdown`) |
| `GET` | `/api/dataset/examples` | Contribute UI examples (`?posture=&limit=` — default/max 50 per posture) |
| `POST` | `/api/dataset/contribute` | CC-BY contribution (`prompt`, `response`, `posture`) |
| `GET` | `/api/audit/recent` | Recent audit events |
| `GET` | `/api/edition/status` | Open-core / Pro packaging + managed hosting hooks |
| `GET`/`POST` | `/api/edition/heartbeat` | Control-plane heartbeat payload / ping |
| `GET` | `/api/rbac/me` | Current role / org (when RBAC enabled) |

Mission `POST /api/run` also accepts `posture` (`aggressive`\|`defensive`\|`balanced`) and optional `playbook`.

See [`OPEN_CORE.md`](OPEN_CORE.md), [`training/README.md`](../training/README.md).

---

## Related modules (not HTTP)

| Module | Role |
|--------|------|
| `tools.waf_evasion` | Outbound scan evasion profiles |
| `tools.sql_injection` | sqlmap technique/intensity builder |
| `tools.cve_exploit_map` | CVE / open-port → MSF modules |
| `tools.payload_strategy` | PAYLOAD + LHOST/LPORT |

See also: [`user_manual.md`](user_manual.md), [`waf_evasion.md`](waf_evasion.md), [`sql_injection.md`](sql_injection.md), root [`README.md`](../README.md).
