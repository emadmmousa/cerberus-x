# Firebreak User Manual

Authorized security testing only. Use Firebreak exclusively against systems you are explicitly permitted to test.

## Overview

Firebreak orchestrates scanners and Metasploit through Celery workers. You launch missions from **Mission Control** (or APIs / MCP). Optional local **Ollama** (`firebreak` model) plans dual-posture next steps (aggressive + defensive). Results stream to the UI via Socket.IO + polling.

## Quick start

1. Copy `.env.example` → `.env` and set at least `MSF_RPC_PASSWORD` and preferably `FIREBREAK_LHOST`.
2. From the repo root:

```bash
docker compose up -d
docker compose run --rm ollama-pull   # builds firebreak persona
```

3. Open Mission Control: [http://localhost:5000](http://localhost:5000)
4. Enter an authorized target, pick posture / playbook, start the mission.

Host-only Ollama: set `FIREBREAK_LLM_BASE_URL=http://host.docker.internal:11434/v1`.

## Mission Control (Focus Launch)

| Control | Purpose |
|---------|---------|
| **Target** | Hostname or URL in scope |
| **Posture** | `balanced` / `aggressive` / `defensive` (maps to playbook) |
| **Playbook** | YAML mission (auto-suggested from posture; override in picker) |
| **Stealth / evasion** | Maps to WAF profiles: `off` → `aggressive` |
| **AI Mode** | Planner + follow-on tools (risky tools allowed by default) |
| **Proxy** | Route web tools via Oxylabs (optional) |
| **NL goal** | Natural-language objective for AI planning |

Default playbooks use **`evasion: aggressive`** and heavy web/CVE coverage when posture allows.

## Mission Control (Firebreak panels)

Open **Options** to see Firebreak status strips:

| Panel | What it shows |
|-------|----------------|
| **Firebreak model** | Primary/fallback scaffolds, latency + `$/1k`, multi-scaffold / cost-route badges, SSO |
| **Marketplace** | Catalog of scaffold recipes; **Pro** can Register / Remove live OpenAI-compat endpoints |
| **Refresh** | Re-probe scaffold health |
| **Dataset contribute** | CC-BY prompt/response pairs (filter examples by posture); **Load all (posture)** / **Submit all (CC-BY)** for bulk staging |
| **Blackboard** | Shared mission facts (`findings`, `proposed_action`, `hardening`, `consensus`) |
| **Audit** | Recent events (scaffold disagreements, contributions, auth) |
| **Auth** | Sign in via Auth0 / OIDC when configured |

After an AI mission finishes, Mission Summary lists **Defense recommendations** with **Export markdown**.

### Dataset bulk contribute

In the Firebreak **Dataset contribute** panel, pick a posture filter, then:

1. **Load all (posture)** — stages every example returned for the current posture into a checklist (all checked by default). Status shows `Bulk: N/N ready`.
2. **Submit all (CC-BY)** — submits each checked row via the existing contribute API (`CC-BY-4.0`, contributor `mission-control`). Shows `Saved X/Y` or partial errors; empty prompt/response rows are skipped.

Single-example load into the text areas still works as before.

### Dual posture

| Posture | Playbook | Behavior |
|---------|----------|----------|
| **balanced** | `balanced_offense_defense.yaml` | Offense when justified + hardening recs |
| **aggressive** | `complete_dark_arsenal.yaml` | Full offense arsenal / proof-of-impact |
| **defensive** | `defensive_audit.yaml` | Exposure scanners only (no sqlmap/MSF/hydra…) |

## What runs in a mission

1. Orchestrator loads playbook (or AI plan) and enqueues Celery tasks.
2. Workers run wrappers (`nmap`, `nuclei`, `sqlmap`, `metasploit`, …).
3. **DecisionEngine** may add CVE→MSF exploits, sqlmap dump/enum, and post-ex modules (respecting posture).
4. Multi-scaffold consensus (when enabled) merges or picks plans; disagreements go to Audit + Blackboard.
5. **WAF evasion** injects headers, delays, tampers (see `docs/waf_evasion.md`).
6. **SQLi strategy** upgrades sqlmap when intensity is high (see `docs/sql_injection.md`).

## AI / Ollama (Firebreak)

| Env | Default | Meaning |
|-----|---------|---------|
| `FIREBREAK_LLM_BASE_MODEL` | `qwen2.5:7b` | Open base for own Firebreak model |
| `FIREBREAK_LLM_MODEL` | `firebreak` | Built from `docker/ollama/Modelfile` |
| `FIREBREAK_MULTI_SCAFFOLD` | `true` | Query primary + fallback (+ optional EXTRA) |
| `FIREBREAK_SCAFFOLD_COST_ROUTE` | `false` | Prefer cheaper scaffolds first |
| `FIREBREAK_LLM_THINK` | `false` | Disable thinking traces for clean JSON plans |
| `FIREBREAK_LLM_UNRESTRICTED` | `true` | Aggressive prompts + higher temperature |
| `FIREBREAK_AI_REQUIRE_CONFIRM` | `false` | High-risk tools run without extra confirm |
| `FIREBREAK_EDITION` | `community` | `pro` unlocks marketplace register + hosting hooks |

If Ollama is down, the heuristic planner still proposes recon → vuln → (posture-filtered) follow-ons.

## Payloads & shells

Reverse sessions need a reachable callback:

```bash
FIREBREAK_LHOST=<your-reachable-ip>
FIREBREAK_LPORT_START=4444
FIREBREAK_PAYLOAD_PREFER=reverse   # or bind
```

See `docs/superpowers/specs/2026-07-20-payload-strategy-design.md`.

## Active scanner API

Lightweight probes (SQLi/XSS/NoSQL/path/open-redirect) with optional authz allowlist:

- `POST /api/scan/start`
- `GET /api/scan/status/<job_id>`

Set `FIREBREAK_REQUIRE_AUTHZ=true` and maintain `authorized_targets.json` (see `authorized_targets.example.json`).

## Sessions & authentication

When Redis is available, Mission Control uses **server-side Flask sessions** stored under the `firebreak:sess:` prefix (not a signed cookie payload). Each authenticated user gets an isolated session that works across orchestrator replicas.

| Env | Default | Meaning |
|-----|---------|---------|
| `SECRET_KEY` | `change-me` in `.env.example` | Signs session cookies; must not stay at the insecure default `firebreak-secret` in production |
| `FIREBREAK_SESSION_SECURE` | `false` | Set `true` when serving over HTTPS so session cookies get the `Secure` flag |

If Redis or Flask-Session is unavailable, the orchestrator falls back to signed cookie sessions and logs a warning (fine for local labs).

Admin → **Ops** shows `secret_key_insecure` when `SECRET_KEY` is still the default — change it before enforcing RBAC in production.

## Admin → Ops automation

Open **Admin** (admin role) and select the **Ops** tab to toggle background jobs without redeploying:

| Control | When ON | Schedule |
|---------|---------|----------|
| **Auto-Scale** | Celery beat adjusts worker pool sizing | Every ~30s |
| **Auto-Train** | Daily merge + eval pipeline; QLoRA only when `FIREBREAK_TRAIN_GPU=true` | Crontab hour from `FIREBREAK_AUTO_TRAIN_HOUR` (default 3 UTC) |
| **Learning Tick** | Harvests completed missions into `output/dataset/harvest.jsonl` and refreshes scaffold health | Every ~60s |

Each control has **ON**, **OFF**, or **Defer** (use deployment env vars). Effective state is shown under each row. Resolution order: Admin override → env → `false` (all off by default).

**Celery beat** must be running (exactly one scheduler replica) for these periodic tasks to fire. Compose ships a dedicated `beat` service; do not add `-B` to worker replicas or you will run duplicate schedulers.

| Env | Default | Meaning |
|-----|---------|---------|
| `FIREBREAK_AUTO_SCALE` | `false` | Defer path for Auto-Scale |
| `FIREBREAK_AUTO_TRAIN` | `false` | Defer path for daily ML pipeline |
| `FIREBREAK_AUTO_TRAIN_HOUR` | `3` | Hour (UTC) for daily pipeline |
| `FIREBREAK_LEARNING_TICK` | `false` | Defer path for per-minute harvest |
| `FIREBREAK_TRAIN_GPU` | `false` | Allow real QLoRA in daily pipeline (otherwise dry-run only) |

**Manual scale** is always available: `POST /api/scale/auto` runs a one-shot worker scale hint regardless of the Auto-Scale beat flag.

With Learning Tick ON, a finished mission typically appears in harvest JSONL within ~1–2 minutes. With Auto-Train ON, a dry-run report lands under `output/ml/` after the scheduled hour.

## Reporting & ops

- Health: `GET /health`, `GET /ready`, `GET /metrics`
- Admin settings / Ops toggles: `GET /api/admin/settings`, `PUT /api/admin/settings/ops` (see `docs/api_reference.md`)
- Proxy UI/API under `/api/proxy/*`
- Firebreak APIs: see `docs/api_reference.md` (Firebreak section)
- Helm: `helm/firebreak/README.md`
- Logs: `docker compose logs -f orchestrator worker`

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Blank / old UI | Hard refresh; rebuild SPA: `cd frontend && npm run build` |
| No scaffolds | Set `FIREBREAK_LLM_BASE_URL` (Compose default `http://ollama:11434/v1`) |
| No reverse shell | `FIREBREAK_LHOST` reachable from target |
| sqlmap soft | Confirm `FIREBREAK_SQLI_INTENSITY=aggressive` and evasion level |
| AI refuses / quiet | Recreate model: `docker compose run --rm ollama-pull` |
| Instant/cloud 401 | Set `OLLAMA_API_KEY` from https://ollama.com/settings/keys, recreate `ollama` |
| MSF module missing | Update Metasploit image / `msfupdate` inside container |
| Marketplace register 403 | Set `FIREBREAK_EDITION=pro` |

Full reference: root [`README.md`](../README.md), [`OPEN_CORE.md`](OPEN_CORE.md).
