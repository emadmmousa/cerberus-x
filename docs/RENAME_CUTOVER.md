# Firebreak rename cutover

Hard cutover from Cerberus-X. There is **no** dual-read of old `CERBERUS_*` env, Redis keys, or headers.

## Domains

| Role | Value |
|------|-------|
| Canonical site | `https://firebreak.com` |
| Application | `https://app.firebreak.com` |
| Redirects | `firebreak.net`, `firebreak.org`, `firebreak.info` → `https://firebreak.com` |

Configure DNS + TLS outside this repo. Point Helm ingress / CDN to `app.firebreak.com`. Set Auth0 (or OIDC) Allowed Callback/Logout/Web Origins to `https://app.firebreak.com`.

## Operator checklist

1. **Backup** job results DB, contribution JSONL, and any custom Helm values.
2. **Stop** old compose/Helm release (`cerberus` / `cerberus-x` namespace).
3. **Rename env** — copy `.env.example` keys; every `CERBERUS_*` becomes `FIREBREAK_*`. Set `APP_BASE_URL=https://app.firebreak.com` in production.
4. **Redis** — flush or accept empty `firebreak:*` keys (sessions, jobs, admin settings, scaffolds). Old `cerberus:*` keys are ignored.
5. **Images** — build/push `emadmmousa/firebreak-{orchestrator,worker,metasploit}` (or your registry).
6. **Model** — rebuild Ollama model `firebreak` from `docker/ollama/Modelfile` (`docker compose run --rm ollama-pull` or equivalent).
7. **Deploy** — `helm upgrade --install firebreak ./helm/firebreak -n firebreak --create-namespace` (or compose up).
8. **Auth0** — update callbacks to `/callback` (and OIDC paths) under `https://app.firebreak.com`.
9. **Grafana** — panels must query `firebreak_*` metrics.
10. **GitHub** — rename repository to `firebreak`; update remotes; optionally `mv cerberus-x firebreak` locally.
11. **Clients** — send `X-Firebreak-Role` / `X-Firebreak-Org` instead of `X-Cerberus-*`.

## AI Lab

The former product-feature page **Firebreak** is now **AI Lab**:

- UI: `/ai-lab`
- API: `GET /api/ai-lab/status`

## Verify

```bash
rg -i 'cerberus' --glob '!.git/**' --glob '!**/node_modules/**' --glob '!**/.venv/**'
# expect: no matches in tracked product sources
PYTHONPATH=src pytest -q
cd frontend && npm test -- --run && npm run build
```
