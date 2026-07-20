# Cerberus-X Developer Guide

## Architecture

```text
Mission Control (React) ──► Flask orchestrator
                              ├── Celery → workers → tool wrappers
                              ├── DecisionEngine (CVE / SQLi / post-ex)
                              ├── AI planner + memory (Ollama optional)
                              ├── MCP JSON-RPC (/mcp)
                              └── SQLite results (+ optional Redis/ES)
```

| Package | Role |
|---------|------|
| `src/orchestrator/` | Flask app, Celery tasks, AI, MCP, scan API, dashboard |
| `src/tools/` | Wrappers, proxy, `waf_evasion`, `sql_injection`, payloads, CVE map |
| `src/scanner/` | `VulnerabilityScanner` + authorization enforcer |
| `src/security/` | Platform WAF middleware, audit, vault helpers |
| `src/workers/` | Dynamic tool runner |
| `frontend/` | Vite + React Mission Control |
| `playbooks/` | YAML missions |
| `docker/` | Compose extras, Ollama Modelfile, Vault |

State is primarily **SQLite** (`results.db`) and in-memory job maps; Redis backs Celery. Postgres is used by the Metasploit service, not as the primary app DB.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export PYTHONPATH=src
pytest -q

cd frontend && npm ci && npm test -- --run && npm run build
```

Compose (full stack):

```bash
cp .env.example .env
docker compose up -d
docker compose run --rm ollama-pull
```

## Adding a tool wrapper

1. Add `src/tools/wrappers/mytool.py` with a `scan(target, args=None, use_proxy=False, proxy_protocol="http", evasion=None)` style entrypoint.
2. Register the Celery task in `src/orchestrator/tasks.py` (`_TASK_MAP`).
3. Expose in MCP allowlist (`src/orchestrator/mcp/registry.py`) if needed.
4. Add playbook usage + tests under `tests/`.

Prefer HTTPS-first URL helpers (`tools.wrappers._web_url`) and proxy merge (`tools.wrappers._proxy`).

## WAF evasion & SQLi

- Profiles: `tools.waf_evasion.evasion_profile(level, target_waf=...)`
- Inventory: `list_techniques()`
- sqlmap merge: `tools.sql_injection.build_sqlmap_args(profile, existing=..., evasion=...)`
- Intensity: `CERBERUS_SQLI_INTENSITY` or evasion level via `resolve_sqli_intensity()`

Docs: [`waf_evasion.md`](waf_evasion.md), [`sql_injection.md`](sql_injection.md).

## AI / LLM

- Client: `orchestrator.ai.llm.chat_completion`
- Prompts: `orchestrator.ai.prompts` (`CERBERUS_LLM_UNRESTRICTED`)
- Safety gate: `orchestrator.ai.safety.require_confirm_for_tool` (default confirm **off**)
- Modelfile: `docker/ollama/Modelfile` → model name `cerberus-x`

## Payloads & exploits

- `tools.payload_strategy.resolve_exploit_options` — PAYLOAD / LHOST / LPORT
- `tools.cve_exploit_map` — CVE and open-port → Metasploit modules
- Decision engine queues exploits/post without interactive confirm in mission flow

## Testing

```bash
PYTHONPATH=src pytest -q
cd frontend && npm test -- --run
```

CI: `.github/workflows/ci.yml` (unit + selected integration + frontend).

## Security notes for contributors

- Never commit `.env`, `results.db`, or real `authorized_targets.json`.
- Do not add raw HTTP request-smuggling / RST exploit PoCs into wrappers; keep protocol-level gaps documented in `list_techniques()["not_implemented_protocol"]`.
- Outbound “WAF evasion” is for **authorized** target testing — distinct from the optional inbound orchestrator WAF in `security.waf`.
