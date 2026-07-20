# Cerberus-X User Manual

Authorized security testing only. Use Cerberus-X exclusively against systems you are explicitly permitted to test.

## Overview

Cerberus-X orchestrates scanners and Metasploit through Celery workers. You launch missions from **Mission Control** (or APIs / MCP). Optional local **Ollama** (`cerberus-x` model) plans aggressive next steps. Results stream to the UI via Socket.IO + polling.

## Quick start

1. Copy `.env.example` → `.env` and set at least `MSF_RPC_PASSWORD` and preferably `CERBERUS_LHOST`.
2. From the repo root:

```bash
docker compose up -d
docker compose run --rm ollama-pull   # builds cerberus-x persona
```

3. Open Mission Control: [http://localhost:5000](http://localhost:5000)
4. Enter an authorized target, pick a playbook / Focus Launch options, start the mission.

Host-only Ollama: set `CERBERUS_LLM_BASE_URL=http://host.docker.internal:11434/v1`.

## Mission Control (Focus Launch)

| Control | Purpose |
|---------|---------|
| **Target** | Hostname or URL in scope |
| **Playbook** | YAML mission (`default`, `ultimate_aggression`, …) |
| **Stealth / evasion** | Maps to WAF profiles: `off` → `aggressive` |
| **AI Mode** | Planner + follow-on tools (risky tools allowed by default) |
| **Proxy** | Route web tools via Oxylabs (optional) |
| **NL goal** | Natural-language objective for AI planning |

Default playbooks use **`evasion: aggressive`** and heavy web/CVE coverage.

## What runs in a mission

1. Orchestrator loads playbook (or AI plan) and enqueues Celery tasks.
2. Workers run wrappers (`nmap`, `nuclei`, `sqlmap`, `metasploit`, …).
3. **DecisionEngine** may add CVE→MSF exploits, sqlmap dump/enum, and post-ex modules.
4. **WAF evasion** injects headers, delays, tampers, HPP, origin hints (see `docs/waf_evasion.md`).
5. **SQLi strategy** upgrades sqlmap to BEUSTQ + enumeration/dump when intensity is high (see `docs/sql_injection.md`).

## AI / Ollama

| Env | Default | Meaning |
|-----|---------|---------|
| `CERBERUS_LLM_MODEL` | `cerberus-x` | Unrestricted offensive persona Modelfile |
| `CERBERUS_LLM_UNRESTRICTED` | `true` | Aggressive prompts + higher temperature |
| `CERBERUS_AI_REQUIRE_CONFIRM` | `false` | High-risk tools run without extra confirm |

If Ollama is down, the heuristic planner still proposes recon → vuln → sqlmap/metasploit.

## Payloads & shells

Reverse sessions need a reachable callback:

```bash
CERBERUS_LHOST=<your-reachable-ip>
CERBERUS_LPORT_START=4444
CERBERUS_PAYLOAD_PREFER=reverse   # or bind
```

See `docs/superpowers/specs/2026-07-20-payload-strategy-design.md`.

## Active scanner API

Lightweight probes (SQLi/XSS/NoSQL/path/open-redirect) with optional authz allowlist:

- `POST /api/scan/start`
- `GET /api/scan/status/<job_id>`

Set `CERBERUS_REQUIRE_AUTHZ=true` and maintain `authorized_targets.json` (see `authorized_targets.example.json`).

## Reporting & ops

- Health: `GET /health`, `GET /ready`, `GET /metrics`
- Proxy UI/API under `/api/proxy/*`
- Logs: `docker compose logs -f orchestrator worker`

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Blank UI | Rebuild SPA: `cd frontend && npm run build` |
| No reverse shell | `CERBERUS_LHOST` reachable from target |
| sqlmap soft | Confirm `CERBERUS_SQLI_INTENSITY=aggressive` and evasion level |
| AI refuses / quiet | Recreate model: `docker compose run --rm ollama-pull` |
| MSF module missing | Update Metasploit image / `msfupdate` inside container |

Full reference: root [`README.md`](../README.md).
