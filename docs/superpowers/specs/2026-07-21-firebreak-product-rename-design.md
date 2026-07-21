# Firebreak Product Rename — Design

**Date:** 2026-07-21  
**Status:** Approved for planning  
**Repo (today):** `emadmmousa/firebreak` → becomes `emadmmousa/firebreak`

## Problem

The product is still branded Firebreak across UI, docs, env vars, Redis keys, headers, Docker/Helm, metrics, and the GitHub repository, while Firebreak already names the AI feature path. The operator intends to ship as **Firebreak** on `firebreak.com` / `.net` / `.org` / `.info`, with a hard cutover (no Firebreak aliases).

## Goals

- Product identity is Firebreak everywhere in the tracked tree.
- Canonical public domain: `https://firebreak.com`.
- Application origin: `https://app.firebreak.com`.
- `firebreak.net`, `firebreak.org`, `firebreak.info` permanently redirect to `https://firebreak.com`.
- AI feature formerly called “Firebreak” becomes **AI Lab** at `/ai-lab`.
- GitHub repository renamed to `firebreak`; clone and image URLs updated.
- Zero tracked `Firebreak` / `firebreak` / `FIREBREAK` identifiers remain after cutover (excluding `.git` history and third-party caches).

## Non-goals

- Rewriting historical Git commits.
- Dual-read / dual-write compatibility with old `FIREBREAK_*` env, Redis keys, or headers.
- Completing live DNS/registrar/TLS/CDN redirect infrastructure inside this repository alone (repo ships config + runbook; operators apply DNS).
- Renaming Python import packages (`orchestrator`, `security`, `tools`) solely for branding.

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Compatibility | Hard cutover — no Firebreak aliases |
| Canonical TLD | `firebreak.com` |
| Other TLDs | Permanent redirect → `firebreak.com` |
| App host | `app.firebreak.com` |
| Former Firebreak AI UI | **AI Lab**, route `/ai-lab` |
| Repository | Rename GitHub repo to `firebreak` |

## Approach

**Atomic hard cutover** on one release branch, applied in dependency-ordered commits (not blind global search-replace). Existing deployments require explicit migration (env rename, Redis/session reset, image/model rebuild, Helm reinstall).

---

## 1. Identifier mapping

### Display / copy

| From | To |
|------|-----|
| Firebreak, Firebreak, Firebreak | Firebreak |
| Firebreak (persona / labels) | Firebreak |
| Nav “Firebreak” (AI page) | AI Lab |

### Routes and APIs

| From | To |
|------|-----|
| SPA `/firebreak` | `/ai-lab` |
| `GET /api/ai-lab/status` | `GET /api/ai-lab/status` |
| Frontend `Firebreak.tsx`, `AiLabPanel.tsx`, `getAiLabStatus()` | `AiLab.tsx`, `AiLabPanel.tsx`, `getAiLabStatus()` |
| Tests `test_firebreak_*`, `AiLabPanel.bulk.test.tsx` | `test_ai_lab_*`, `AiLabPanel.bulk.test.tsx` |

Optional: temporary HTTP 308 from `/firebreak` → `/ai-lab` and `/api/ai-lab/status` → `/api/ai-lab/status` for one release is **out of scope** under hard cutover; omit redirects unless later requested.

### Configuration

| From | To |
|------|-----|
| `FIREBREAK_*` env vars | `FIREBREAK_*` (same suffixes) |
| Default secret token `firebreak-secret` | `firebreak-secret` (still treated as insecure default) |
| Insecure-secret set | `{firebreak-secret, change-me, ""}` |

### HTTP / session claims

| From | To |
|------|-----|
| `X-Firebreak-Role` | `X-Firebreak-Role` |
| `X-Firebreak-Org` | `X-Firebreak-Org` |
| Claim / session `firebreak_role` | `firebreak_role` |
| Flask `g.firebreak_role` | `g.firebreak_role` |

### Redis / storage keys

| From | To |
|------|-----|
| `firebreak:sess:` | `firebreak:sess:` |
| `firebreak:job:` | `firebreak:job:` |
| `firebreak:proxy:settings` | `firebreak:proxy:settings` |
| `firebreak:scaffolds`, `firebreak:scaffold:*` | `firebreak:scaffolds`, `firebreak:scaffold:*` |
| `firebreak:admin:*` | `firebreak:admin:*` |
| `firebreak:ml:harvested` | `firebreak:ml:harvested` |
| `firebreak:mcp:*` (and related MCP keys) | `firebreak:mcp:*` |
| Theme localStorage `firebreak-theme` | `firebreak-theme` |

Blackboard `bb:` stays brand-neutral.

### Observability

| From | To |
|------|-----|
| Prometheus `firebreak_*` | `firebreak_*` |
| ES / Splunk defaults `firebreak-audit`, `firebreak-results` | `firebreak-audit`, `firebreak-results` |
| Grafana dashboard title / queries | Firebreak + `firebreak_*` |

### Model / scaffolds / dataset

| From | To |
|------|-----|
| Ollama model `firebreak` | `firebreak` |
| Scaffold id `ollama-primary` | `ollama-primary` |
| HF / Makefile `firebreak/firebreak-v0` | `firebreak/firebreak-v0` |
| Training seed persona strings | Firebreak / AI Lab as appropriate |

### Packaging / deploy

| From | To |
|------|-----|
| npm `firebreak-console` | `firebreak-console` |
| Images `emadmmousa/firebreak-*` | `emadmmousa/firebreak-*` |
| Compose containers `firebreak-*` | `firebreak-*` |
| Helm chart dir / name `firebreak` | `firebreak` |
| Namespace / release `firebreak` / `firebreak` | `firebreak` |
| Secrets / CM `firebreak-*` | `firebreak-*` |
| OS user `firebreak` in Dockerfiles | `firebreak` |
| `init_firebreak.py` / setup name | `init_firebreak.py` / `firebreak` |
| MCP `serverInfo.name` `firebreak` | `firebreak` |
| User-Agent strings | `firebreak/...` |

### Domains (config + docs)

| Role | Value |
|------|-------|
| Canonical site | `https://firebreak.com` |
| App | `https://app.firebreak.com` |
| Redirect sources | `firebreak.net`, `firebreak.org`, `firebreak.info` → `https://firebreak.com` |
| Defaults | `APP_BASE_URL=https://app.firebreak.com` in prod examples; Auth0/OIDC callbacks under that origin; Helm ingress host `app.firebreak.com` |

---

## 2. Frontend

- Replace brand in `frontend/index.html`, `AppShell`, `Login`, Admin copy, aria labels, and related views.
- Rename AI Lab files, routes (`routes.tsx`), client helpers, and tests.
- Rebuild `src/orchestrator/static/app/**` via Vite (`make frontend-build` / `npm run build`); never hand-edit hashed assets.
- Update `frontend/package.json` name and lockfile.
- Add a CI/test check that fails if tracked frontend **source** contains forbidden brand tokens.

---

## 3. Backend and operations

- Rename env reads/writes, defaults in `.env.example`, compose, Helm values/templates, K8s manifests, CLI, MCP identity, audit/ES clients, metrics, Redis prefixes, session config, admin store, ML harvest keys, prompts, Modelfile, marketplace labels, and user agents.
- Update security modules (`rbac`, Auth0/OIDC claim mapping, packaging headers).
- No dual-read: missing `FIREBREAK_*` does not fall back to `FIREBREAK_*`.
- Provide `docs/RENAME_CUTOVER.md` (or section in developer/user manuals) covering: backup, tear down old Helm/compose resources, rename env, flush or accept empty Redis session/job/admin keys, rebuild/pull `firebreak` model, retag/push images, reinstall chart, update Auth0 allowed callbacks/origins.

---

## 4. Documentation and repository identity

- Update README, manuals, API reference, ROADMAP, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, training cards, MkDocs `site_name`, and current superpowers plans/specs that describe the living product (historical dated filenames may keep their date prefix; body text uses Firebreak).
- After code merge: rename GitHub repository `firebreak` → `firebreak`; update remote URLs; document local folder rename (`mv firebreak firebreak`).
- Do not rewrite Git history.

---

## 5. Testing and acceptance

| Check | Pass criteria |
|-------|----------------|
| Backend pytest | Suites updated for `FIREBREAK_*`, headers, metrics, model id, MCP name |
| Frontend vitest | Brand + AI Lab route/tests green |
| Frontend production build | Static app rebuilt and committed if repo tracks it |
| Compose / Helm dry validation | Services and chart render under `firebreak` names |
| Forbidden-name scan | Zero matches for `Firebreak`, `firebreak`, `FIREBREAK`, `firebreak` in tracked source (allowlist only if an external third-party string is proven unavoidable—prefer zero) |
| Domain runbook | Documents redirect + `APP_BASE_URL` / ingress / Auth0 steps for all four TLDs |

## Error handling / migration risk

- Hard cutover **will** invalidate existing Redis sessions, admin settings, job keys, Grafana panels wired to old metrics, and any external clients using old headers or env.
- Operators must follow the cutover runbook; there is no automatic migration of Redis key namespaces.
- Image registries may still hold old tags until deleted manually; docs warn not to mix old/new tags.

## Rollout order (implementation slices)

1. Env/config mapping + `.env.example` + session/Redis/header/metrics core libraries.
2. Backend APIs (AI Lab status route), MCP, prompts, Modelfile, marketplace, training scripts.
3. Frontend rename + rebuild static assets.
4. Docker Compose + Helm/K8s + deploy scripts.
5. Docs + cutover runbook + forbidden-name CI check.
6. External: GitHub repo rename, DNS/redirects, Auth0 dashboard, image push under new names.

## Success criteria

- Operator opens the SPA and sees only **Firebreak** branding; AI controls live under **AI Lab** at `/ai-lab`.
- Fresh compose/Helm install uses only `FIREBREAK_*` and `firebreak-*` resources.
- Ollama default model is `firebreak`.
- Tracked tree scan finds no Firebreak brand tokens.
- Docs state `firebreak.com` as canonical and describe redirects for the other three TLDs.
