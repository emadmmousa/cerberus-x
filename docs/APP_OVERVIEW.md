# Firebreak — Product Overview

**Authorized security testing orchestrator.** Firebreak runs on your infrastructure (Docker on localhost by default), coordinates offensive and defensive security tools through Celery workers, and exposes a React **Mission Control** UI plus HTTP/MCP APIs.

> **Legal:** Use only against systems you are explicitly authorized to test.

---

## What Firebreak Does

Firebreak turns an **engagement target** into a multi-phase security mission:

1. **Plan** — YAML playbook, AI planner, or conversational chat agent proposes phases and tools.
2. **Execute** — Celery workers run wrapped CLI tools and Metasploit modules in parallel or sequence.
3. **Adapt** — DecisionEngine and optional LLM re-plan based on findings (open ports, CVEs, SQLi, etc.).
4. **Report** — Results land in SQLite, stream live via Socket.IO, and surface as human-readable summaries and hardening recommendations.

It is **not** a hosted SaaS. The dashboard binds to `127.0.0.1:5000`. Metasploit RPC and Postgres stay on the internal Docker network.

---

## Who It Is For

| Persona | Typical use |
|---------|-------------|
| **Red team / pentest operators** | Full kill-chain missions against in-scope targets |
| **Defensive / audit engineers** | Exposure and misconfiguration assessment with hardening output |
| **Lab operators** | Juice Shop, DVWA, HTB-style targets with training datasets |
| **Security leads / admins** | RBAC, authorized-target lists, audit logs, org isolation (when enabled) |

---

## Core Value Propositions

| Capability | Description |
|------------|-------------|
| **Unified arsenal** | 30+ Celery-mapped tools (nmap, nuclei, sqlmap, Metasploit, OSINT scrapers, AD helpers, …) from one console |
| **Dual posture** | Aggressive offense, balanced mix, or defensive audit — each maps to a default playbook |
| **AI-assisted planning** | Local Ollama (`firebreak` model) or heuristics plan next phases; chat agent for natural-language missions |
| **OSINT + breach intel** | Person-centric intelligence (names, emails, usernames) with Tor dark-web search and commercial-branded breach lookups |
| **Mission chat** | Two-turn playbook flow: pick a template, send target in the next message, confirm to launch |
| **MCP for agents** | External AI clients invoke tools via JSON-RPC with session scoping |
| **Open-core** | Community edition includes the full scanner arsenal; Pro adds packaging hooks (SSO, marketplace register) — see [OPEN_CORE.md](OPEN_CORE.md) |

---

## Editions

| Edition | Env | Notes |
|---------|-----|-------|
| **Community** (default) | `FIREBREAK_EDITION=community` | Full wrappers, Firebreak model, Blackboard, multi-scaffold |
| **Pro** | `FIREBREAK_EDITION=pro` | Same core + SSO/RBAC packaging, managed hosting heartbeat, scaffold marketplace registration |

Scanning capability is **not** paywalled in community.

---

## Major Surfaces

| Surface | URL / entry | Purpose |
|---------|-------------|---------|
| **Mission Control SPA** | `http://127.0.0.1:5000` | Primary operator UI |
| **REST API** | `/api/*` | Missions, chat, catalog, admin, OSINT |
| **MCP** | `POST /mcp` | Agent tool invocation |
| **CLI** | `python -m orchestrator.cli` | Headless playbook runs |
| **Socket.IO** | Same origin as dashboard | Live activity and Metasploit console |

---

## Security Model (Summary)

Two independent layers:

1. **Identity / RBAC** (`FIREBREAK_RBAC_ENFORCE`) — Who can log in and what role they have (admin → operator → viewer). Default **off** for lab use.
2. **Engagement authorization** (`FIREBREAK_REQUIRE_AUTHZ`) — Which targets/seeds may be scanned. Default **off**; when on, targets must appear in `authorized_targets.json`.

Both can be enabled together for production-style deployments. See [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md).

---

## Quick Start

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD, MSF_RPC_PASSWORD

docker compose up -d
curl -s http://127.0.0.1:5000/health
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) → **Missions** → chat, manual launch, or prompt deck.

Full operator steps: [user_manual.md](user_manual.md). Architecture: [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Documentation Map

| Document | Contents |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Services, data flow, backend modules |
| [FEATURES.md](FEATURES.md) | Feature catalog and tool arsenal |
| [USER_JOURNEYS.md](USER_JOURNEYS.md) | UI pages and operator workflows |
| [MISSION_AND_CHAT.md](MISSION_AND_CHAT.md) | Playbooks, AI loop, chat agent lifecycle |
| [OSINT_INTEL.md](OSINT_INTEL.md) | Seeds, dark web, breach providers |
| [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md) | RBAC, authz, audit |
| [../README.md](../README.md) | Install, env, troubleshooting |
| [api_reference.md](api_reference.md) | HTTP/MCP endpoints |
