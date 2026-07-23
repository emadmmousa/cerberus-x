# Firebreak — Features

Complete catalog of product capabilities, tools, and optional modules.

---

## Mission Execution

| Feature | Description |
|---------|-------------|
| **YAML playbooks** | Multi-phase missions with tool lists, parallelism, dependencies, conditional `when:` gates |
| **Manual launch** | Target + posture + playbook + stealth + optional NL goal from Mission Control |
| **AI adaptive missions** | `run_ai_mission()` loops: plan → execute → DecisionEngine → re-plan until cap or completion |
| **Chat-launched missions** | Natural-language planning with structured `firebreak-plan` blocks and confirm-to-launch |
| **Strike prompts** | Curated one-click templates (recon, web, AD, OSINT decks) |
| **Parallel phases** | Celery `group()` for concurrent tools within a phase |
| **Stop / edit** | Abort running jobs; patch in-flight mission metadata |
| **Live telemetry** | Socket.IO activity feed + HTTP polling on mission detail |

---

## Tool Arsenal (Celery `_TASK_MAP`)

Each tool runs inside worker containers via a Python wrapper under `src/tools/wrappers/`.

### Recon & enumeration

| Tool | Purpose |
|------|---------|
| **nmap** | Port/service discovery |
| **masscan** / **rustscan** / **zmap** | Fast port scanning |
| **gobuster** / **ffuf** | Directory and path fuzzing |
| **whatweb** | Web technology fingerprinting |
| **httpx** | HTTP probing and status checks |
| **katana** | Web crawling |

### Vulnerability & web

| Tool | Purpose |
|------|---------|
| **nuclei** | Template-based CVE/misconfig detection |
| **nikto** | Web server scanner |
| **sqlmap** | SQL injection testing |
| **xsstrike** | XSS detection |

### Exploitation & post-exploit

| Tool | Purpose |
|------|---------|
| **metasploit** | Module execution via msgrpc |
| **hydra** | Online credential brute force |
| **john** / **hashcat** | Offline hash cracking |
| **impacket** | Windows protocol attacks |
| **crackmapexec** | SMB/WinRM lateral movement |
| **responder** | LLMNR/NBT-NS poisoning |
| **bloodhound** | AD attack path collection |
| **sliver** | C2 framework integration |
| **winpeas** / **linpeas** | Local privilege escalation enumeration |

### OSINT & intelligence

| Tool | Purpose |
|------|---------|
| **theharvester** | Email/subdomain harvest (seed-aware) |
| **subfinder** | Passive subdomain discovery |
| **gau** | Known URLs from archives |
| **sherlock** | Username presence on social sites |
| **darkweb** | Tor-backed dark web search |
| **breach_intel** | Credential breach lookups (provider-backed) |

### Custom tools

Operators can register **invented** tools via the AI invention flow; approved entries run through `run_custom_tool_task` when present in `tools_registry`.

---

## Decision Engine

`DecisionEngine` (`decision_engine.py`) evaluates phase results and triggers follow-on actions:

- Open ports → deeper service scans or Metasploit modules
- CVE / nuclei hits → targeted exploitation attempts (posture-dependent)
- SQLi signals → sqlmap depth
- Defensive posture → hardening recommendations on blackboard

Conditions use structured `when:` blocks in playbooks and AI-generated plans.

---

## AI & LLM

| Feature | Description |
|---------|-------------|
| **Local Ollama model** | `firebreak` persona from `docker/ollama/Modelfile` |
| **Heuristic fallback** | Planner works without LLM when Ollama is down |
| **Multi-scaffold routing** | Primary + fallback models; cost/latency badges in UI |
| **Posture-aware tool lists** | Aggressive vs defensive allowlists for LLM scheduling |
| **Chat advisor** | Streaming persona with mission proposals embedded in markdown |
| **AI Lab** | Scaffold health, marketplace, dataset contribution UI |
| **Dataset pipeline** | CC-BY contributions staged for training (`training/dataset/`) |
| **Auto-train** | Optional Celery beat job for fine-tuning (disabled by default) |

---

## OSINT & Breach Intelligence

See [OSINT_INTEL.md](OSINT_INTEL.md) for detail.

| Feature | Description |
|---------|-------------|
| **Seed extraction** | Emails, domains, usernames, full names (incl. Arabic) from chat |
| **OSINT-only missions** | Templates that exclude port scans and exploitation |
| **Two-turn flow** | Pick OSINT deck → send target in next message → confirm launch |
| **Dark web search** | Worker routes through Tor container |
| **Breach providers** | DeHashed-branded as **Breach Vault**, LeakCheck as **Leak Radar** |
| **Target panel** | Frontend `OsintTargetPanel` for seed review before launch |

---

## Mission Chat

| Feature | Description |
|---------|-------------|
| **Thread CRUD** | Create/list/archive chat missions |
| **SSE streaming** | Token stream from advisor LLM |
| **Structured plans** | ` ```firebreak-plan` JSON blocks parsed into proposals |
| **Launch detection** | "Confirmed", "Yes", "launch" preserve prior target (not mis-parsed as username) |
| **Auto-execute** | Optional immediate launch when proposal is complete |
| **Web search** | Optional context enrichment for advisor |

---

## Authentication & Authorization

See [SECURITY_AND_AUTH.md](SECURITY_AND_AUTH.md).

| Feature | Default | Description |
|---------|---------|-------------|
| **Local signup/login** | On | Email/password sessions |
| **Auth0 / OIDC** | Optional | Enterprise SSO when configured |
| **RBAC** | Off | admin / operator / viewer roles |
| **Target authz** | Off | `authorized_targets.json` enforcement |
| **Audit log** | On | Security events in Mission Control |

---

## Admin & Multi-Tenancy Hooks

| Feature | Description |
|---------|-------------|
| **User management** | Create/disable users, assign roles |
| **Organizations** | Org-scoped settings (Pro packaging) |
| **Authorized targets API** | CRUD for engagement allowlist |
| **Ops settings** | Feature flags and deployment metadata |
| **Profile API** | Operator profile preferences |

---

## Integrations

| Integration | Entry |
|-------------|-------|
| **MCP (Model Context Protocol)** | `POST /mcp` — agents invoke `run_tool`, list tools, session scope |
| **Metasploit console** | Socket.IO bridge to msgrpc sessions |
| **Oxylabs proxy** | Optional HTTP proxy for web tools (`_PROXY_TOOLS`) |
| **CLI** | `python -m orchestrator.cli run --playbook …` |
| **Helm / K8s** | Production-style deployment charts |

---

## Frontend Pages

| Route | Feature |
|-------|---------|
| `/` | Marketing landing |
| `/login`, `/signup` | Authentication |
| `/missions` | Chat hub, manual launch, strike prompts |
| `/missions/:id` | Live mission detail, blackboard, OSINT panel |
| `/profile` | User profile |
| `/ai-lab` | Scaffolds, marketplace, dataset |
| `/admin` | Users, targets, audit (role-gated) |
| `/terms`, `/privacy` | Legal pages |

---

## Reporting & Blackboard

| Feature | Description |
|---------|-------------|
| **Phase results** | Raw + summarized tool output per phase |
| **Mission summary** | Aggregated findings; defense recommendations |
| **Export markdown** | Download hardening report |
| **Blackboard** | Shared keys: `findings`, `proposed_action`, `hardening`, `consensus` |
| **Activity timeline** | Real-time operator feed |

---

## Stealth & Evasion

| Setting | Maps to |
|---------|---------|
| **Stealth / evasion UI** | WAF evasion profiles on wrappers |
| **Playbook `evasion`** | Per-phase aggressive/normal profiles |
| **Proxy routing** | Selected web tools via Oxylabs |

---

## Training & Open Dataset

| Path | Purpose |
|------|---------|
| `training/dataset/v0/` | Versioned JSONL examples (aggressive, defensive, balanced) |
| `training/adapters/` | Modelfile / adapter artifacts |
| Mission Control **Dataset contribute** | Bulk CC-BY staging from posture-filtered examples |

---

## Environment-Driven Features

Key toggles in `.env` (see `.env.example`):

| Variable | Effect |
|----------|--------|
| `FIREBREAK_EDITION` | `community` vs `pro` packaging |
| `FIREBREAK_RBAC_ENFORCE` | Require roles on API routes |
| `FIREBREAK_REQUIRE_AUTHZ` | Require targets in allowlist |
| `FIREBREAK_LLM_BASE_URL` | Point planner at host Ollama |
| `FIREBREAK_AI_MODE` | Enable/disable AI planning in missions |
| Breach provider keys | Enable Breach Vault / Leak Radar lookups |

---

## Out of Scope (By Design)

- Hosted multi-tenant SaaS
- Unauthorized scanning
- Automatic cloud target discovery without operator input
- Guaranteed exploit success (tooling is best-effort on authorized targets)
