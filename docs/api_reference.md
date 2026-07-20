# Cerberus-X API Reference

Base URL (compose default): `http://localhost:5000`

Most mission endpoints do **not** require an API key. **MCP** requires `CERBERUS_MCP_API_KEY` when set (Bearer or `X-API-Key`). Optional platform WAF/rate-limit middleware may apply to the orchestrator itself (`CERBERUS_WAF_ENABLED`).

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

## Missions

### `POST /api/run`

Start a playbook or AI mission.

```json
{
  "target": "https://lab.example",
  "playbook": "playbooks/default.yaml",
  "evasion": "aggressive",
  "use_proxy": false,
  "proxy_protocol": "http",
  "ai_mode": false,
  "nl_goal": "",
  "confirm_high_risk": true
}
```

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
| `POST` | `/api/scale/auto` | Worker auto-scale hint |
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

Auth: `Authorization: Bearer <CERBERUS_MCP_API_KEY>` or `X-API-Key`.

High-risk tools (`sqlmap`, `metasploit`, `hydra`, …) require `confirm: true` in the RPC args **only when** `CERBERUS_AI_REQUIRE_CONFIRM=true` (default **false**).

---

## Auth (optional)

| Method | Path | Description |
|--------|------|-------------|
| `*` | `/auth/*` | Optional login helpers when enabled |

---

## Related modules (not HTTP)

| Module | Role |
|--------|------|
| `tools.waf_evasion` | Outbound scan evasion profiles |
| `tools.sql_injection` | sqlmap technique/intensity builder |
| `tools.cve_exploit_map` | CVE / open-port → MSF modules |
| `tools.payload_strategy` | PAYLOAD + LHOST/LPORT |

See also: [`user_manual.md`](user_manual.md), [`waf_evasion.md`](waf_evasion.md), [`sql_injection.md`](sql_injection.md), root [`README.md`](../README.md).
