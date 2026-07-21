# PROJECT FIREBREAK — Firebreak Upgrade Plan

**Date:** 2026-07-21  
**Source:** Firebreak strategic brief (CSI competitive positioning)  
**Repo reality check:** Firebreak today ≠ empty greenfield; map Firebreak onto existing stack.

## Positioning (keep)

> Firebreak / Firebreak: open, extensible, self-hosted AI offensive-security platform — CSI capability without lock-in.

Do **not** claim parity with CSI’s 18TB dataset or `alias2-mini` until Phase 2/3 deliver measured CAIBench numbers.

## Current state vs Firebreak

| Firebreak pillar | Firebreak today | Gap |
|------------------|----------------|-----|
| Apache 2.0 + community | Empty / missing `LICENSE` | Legal + governance |
| Multi-scaffold MCP | MCP = **tool** façade (`/mcp`), one LLM | Scaffold router, registry, consensus |
| Blackboard | Redis = broker/sessions; AI memory = SQLite | Shared multi-agent fact store |
| Specialized LLM | Ollama + Modelfile / Instant cloud | Fine-tune, vLLM, eval harness |
| Open dataset | None | Pipeline + HF release |
| Enterprise | Audit stubs, optional auth | RBAC, SSO, tenancy, HA |
| Tools | **23** Celery wrappers + arsenal playbook | Mature; expand carefully |
| UI | Mission Control | Scaffold/Blackboard visibility |
| CAI | **Rolled back** | Own model `firebreak` |

**Already strong:** tool inventory, DecisionEngine, AI planner+runner, Oxylabs proxy, Metasploit RPC, default full arsenal playbook, Compose + partial K8s.

---

## Reordered delivery (Firebreak-realistic)

Firebreak’s Phase 0→5 is right strategically; for **this app** we compress and reorder so engineering value ships early.

### Wave 0 — Legal & own-model bootstrap

| ID | Work | Outcome |
|----|------|---------|
| W0.1 | Apache-2.0 `LICENSE` | Firebreak claim is true |
| W0.2 | `CONTRIBUTING.md`, `SECURITY.md` | Community entry |
| W0.3 | Public roadmap (GitHub Projects) | Transparency |
| W0.4 | Authorized Modelfile → **`firebreak`** | Own model in Compose |
| W0.5 | ~~CAI profile~~ **CANCELLED** | `training/` + Ollama instead |

**Exit:** License clear; `docker compose run --rm ollama-pull` builds `firebreak`.

### Wave 1 — Multi-scaffold core (6–10 weeks) ≡ Firebreak Phase 1

Build on existing Redis + MCP + DecisionEngine — do **not** rewrite Mission Control.

| ID | Work | Notes |
|----|------|-------|
| W1.1 | **Scaffold adapter interface** | `ScaffoldClient`: `complete()`, `health()`, `cost_estimate()` for Ollama, OpenAI-compat, optional Claude/Codex later |
| W1.2 | **Scaffold registry** | Redis keys: capabilities, latency EMA, enabled flag |
| W1.3 | **MCP proxy / router** | Extend orchestrator MCP or new `/api/scaffolds/*`; route by task type + fallback chain |
| W1.4 | **Blackboard v1** | Redis JSON docs: `bb:{mission_id}:{key}` with TTL, CAS version, pub/sub notify |
| W1.5 | **Consensus** | Best-of-N + confidence; log disagreements to audit |
| W1.6 | Wire **AI planner** to optional multi-scaffold | Default still single model; flag `FIREBREAK_MULTI_SCAFFOLD=true` |
| W1.7 | Wire **DecisionEngine** proposals → Blackboard | Agents write `proposed_action`; engine executes via `_TASK_MAP` only |
| W1.8 | UI: scaffold health + Blackboard findings strip | Mission Control Options / Status |

**Exit:** One mission with Ollama + second OpenAI-compat scaffold; Blackboard R/W p99 &lt; 10ms local; tools still only Firebreak wrappers (safety).

### Wave 2 — Specialized model (8–12 weeks, parallelizable) ≡ Firebreak Phase 2

| ID | Work |
|----|------|
| W2.1 | Lock base: Qwen2.5-7B or Mistral-7B (Apache/permissive) |
| W2.2 | Seed dataset v0 from **our** wrappers: (task → argv → structured result → NL summary) |
| W2.3 | QLoRA fine-tune; export GGUF for Ollama as `firebreak` |
| W2.4 | Eval harness vs planner JSON schema + small internal security Q&A set (CAIBench later) |
| W2.5 | Register as first-class scaffold in Wave 1 registry |

**Exit:** Model runs in Compose; planner quality ≥ heuristic + Instant on internal checklist; no false claim of beating alias2-mini until public CAIBench.

### Wave 3 — Open dataset (ongoing) ≡ Firebreak Phase 3

| ID | Work |
|----|------|
| W3.1 | Dataset repo / HF dataset; DVC or simple version tags |
| W3.2 | Synthetic generator from sandbox targets (authorized lab only) |
| W3.3 | Contribution UI (can be later Mission Control tab) |
| W3.4 | PII redaction + license (CC-BY / ODbL) |

Start **after** W2.2 seed exists. Avoid scraping ToS-hostile sources until legal review.

### Wave 4 — Enterprise (10–16 weeks) ≡ Firebreak Phase 4

| ID | Work |
|----|------|
| W4.1 | App RBAC: Admin / Operator / Viewer on Flask + SPA |
| W4.2 | SSO OIDC (build on `security/auth.py` stubs) |
| W4.3 | Tenant isolation: `org_id` on jobs, results, Blackboard |
| W4.4 | Audit → ES/Splunk (harden existing `security/audit.py`) |
| W4.5 | HA: orchestrator replicas + sticky or shared `playbook_jobs` in Redis |
| W4.6 | Production Helm chart (expand `helm/firebreak/`) |

### Wave 5 — Sustainability ≡ Firebreak Phase 5

Open-core: self-host free; managed hosting + SSO/RBAC as Pro. Marketplace of scaffolds later. **Do not** monetize before Waves 0–1 ship.

---

## What NOT to do in the next 90 days

- Replacing Firebreak `_TASK_MAP` with CAI’s unmanaged shell tools
- Training on scraped exploit PoCs for criminal misuse
- Claiming “beats CSI” without public benchmarks
- Building Discord/website before Apache license + Wave 1 prototype
- Full Alias CAI PRO / `alias1` dependency

---

## 90-day execution plan (concrete)

**Month 1**
1. W0.1–W0.5 (license, CONTRIBUTING, authorized Modelfile, CAI profile)
2. W1.1–W1.4 skeleton (adapter + registry + Blackboard v1 + dual Ollama models as two scaffolds)

**Month 2**
3. W1.5–W1.8 consensus + planner flag + UI strip
4. W2.1–W2.2 dataset seed from wrapper runs

**Month 3**
5. W2.3–W2.5 first `firebreak` GGUF in Compose
6. Start W4.1 RBAC design / spike
7. Internal eval report (honest numbers)

---

## Success metrics (repo-adjusted)

| Metric | 90-day target | 12-month target |
|--------|---------------|-----------------|
| Multi-scaffold mission | 2 scaffolds live | ≥3 + cost routing |
| Blackboard | &lt;10ms local R/W | Cross-replica HA |
| Model | GGUF in Compose | Public CAIBench top-band claim only if measured |
| Community | LICENSE + first external PR | 500★ aspirational |
| Enterprise | RBAC design | Pilot SSO + tenancy |
| Safety | Tools only via wrappers | Same |

---

## Mapping Firebreak phases → Waves

| Firebreak | Firebreak Wave |
|-----------|---------------|
| Phase 0 Foundation | Wave 0 |
| Phase 1 Multi-scaffold | Wave 1 |
| Phase 2 Specialized LLM | Wave 2 |
| Phase 3 Dataset | Wave 3 |
| Phase 4 Enterprise | Wave 4 |
| Phase 5 Commercial | Wave 5 |

## Implementation progress (2026-07-21)

| Wave | Status |
|------|--------|
| W0 | Done — Apache LICENSE, ROADMAP, Firebreak Modelfile, `firebreak` |
| W1 | Done — scaffolds, router, consensus, Blackboard API, Mission Control panel, latency EMA |
| W2 | Done (software path) — expanded seed, QLoRA/GGUF scripts, schema + security QA eval; GPU train still manual |
| W3 | Done (scaffold+) — pipeline, synthetic lab, HF dataset card, `/api/dataset/contribute` + UI |
| W4 | Done+ — RBAC, OIDC login/callback, org-scoped Blackboard+results, Redis job store, ES audit, Helm |
| W5 | Done (hooks) — edition flags, marketplace catalog, control-plane heartbeat; no monetization |

**Alias CAI remains cancelled.** Enable multi-scaffold with `FIREBREAK_MULTI_SCAFFOLD=true`.

### Still deferred / manual

- Real GPU QLoRA run (`python training/scripts/qlora_train.py --no-dry-run` on CUDA host)
- Hugging Face upload (`python training/scripts/publish_dataset.py --upload`)
- Managed hosting / paid Pro packaging

### Continued (2026-07-21 late)

- Dual posture + playbook catalog (`/api/playbooks`, hardening export)
- Auth0 SSO live; `/api/edition/status` Pro packaging hooks
- Multi-scaffold default on (`FIREBREAK_MULTI_SCAFFOLD=true`); Helm Auth0 secret refs
- Mission Control playbook picker + SSO badge on Firebreak panel

### Continued (2026-07-21 night — cybersecurity-aligned)

- **W1.7 fixed:** `DecisionEngine.generate_post_phase_actions` → Blackboard `proposed_action`
- Consensus routing: confidence ≥0.7 → `pick_best`; else merge + disagreement audit
- Blackboard `hardening` + `findings.summary` after YAML and AI missions
- Month-3 honest eval: `training/scripts/eval_report.py` → `training/eval/REPORT.{md,json}`
- Security Q&A expanded (posture, consensus, Auth0, prompt-injection, least privilege)
- Dataset contribute examples UI + `merge_contributions.py` (CC-BY → seed)
- `GET /api/audit/recent` + Mission Control Audit strip

### Continued (2026-07-21 — dual-posture dataset)

- 100 aggressive + 100 defensive seed examples (`training/seed/*_examples.jsonl`)
- `merge_posture_seeds.py` → `posture_merged.jsonl` + `dataset/v0` copies for HF
- `/api/dataset/examples?posture=` + Mission Control posture filter on contribute UI
- QLoRA `--include-posture` trains on dual-posture merge when present

### Continued (2026-07-21 — W5 hooks + GGUF helpers)

- 50 balanced seed examples; triad merged into `posture_merged.jsonl`
- `merge_adapter.py` + `export_gguf.py --write-modelfile` (SYSTEM from docker Modelfile)
- `GET|POST /api/scaffolds/marketplace` (catalog community-readable; register = Pro)
- `GET|POST /api/edition/heartbeat` + Mission Control “Ping control plane”

### Continued (2026-07-21 — wires closed)

- Marketplace registrations merge into live `list_enabled()` / router clients
- Real `cost_estimate` + `FIREBREAK_SCAFFOLD_COST_ROUTE` cheaper-first ordering
- Optional third scaffold via `FIREBREAK_SCAFFOLD_EXTRA_*`
- Helm: `llmBaseUrl`, cost route, audit ES, managed hosting / control plane
- Contribute `posture` persisted → merge/train; QLoRA `--include-community`
- Planner writes Blackboard `consensus`; panel shows confidence/mode

### Continued (2026-07-21 — UX / ops polish)

- AiLabPanel: Pro register form, `$/1k` health, `cost_route` status badge
- Hardening markdown blob download; plan chips show consensus `mode`
- Compose Firebreak env parity; Helm worker Deployment + EXTRA scaffold values
- Root `Makefile` + CI expands Firebreak pytest + eval/publish dry-run
- `docs/api_reference.md` Firebreak endpoint table

### Continued (2026-07-21 — Helm + lifecycle)

- Helm templates: output PVC, Redis, Elasticsearch, Metasploit Service/Deployment
- `DELETE /api/scaffolds/marketplace/<id>` + UI Remove / Refresh
- Nested `docker/docker-compose.yml` aligned to `firebreak` + Firebreak env
- `cost_route` asserted in API tests; CONTRIBUTING / developer_guide Make targets

### Continued (2026-07-21 — software closeout)

- Removed dead Helm `postgres` values; `helm/firebreak/README.md` + deploy.sh note
- MissionControl test mocks for marketplace / edition / OIDC / Auth
- `docs/user_manual.md` Firebreak panels + dual posture

### Continued (2026-07-21 — operator runbooks)

- `training/QLORA_GGUF.md` + `make train-checklist` (dry-run preflight)
- `training/HF_PUBLISH.md` + `publish_dataset.py` card honesty / `HF_TOKEN` gate / `--checklist`
- Authorized lab seeds (`generate_lab_seed.py`) + expanded `security_qa` + seed inventory in eval
- Explicit non-goals: no scraped criminal PoC training; no unbenchmarked CSI claims

**Software path for Waves 0–5 is complete for self-host.** Remaining items are operator/manual only (GPU train, HF upload, real control plane).
