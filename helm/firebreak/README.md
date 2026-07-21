# Firebreak Helm chart (`helm/firebreak`)

Deploys orchestrator, Celery worker, a single Celery beat scheduler, Redis, Elasticsearch (optional), Metasploit RPC, and a shared output PVC.

## Quick install

```bash
./helm/deploy.sh
# or:
helm upgrade --install firebreak ./helm/firebreak -n firebreak --create-namespace
```

## Firebreak values (`firebreak.*`)

| Key | Default | Purpose |
|-----|---------|---------|
| `multiScaffold` | `true` | `FIREBREAK_MULTI_SCAFFOLD` |
| `costRoute` | `false` | Prefer cheaper scaffolds first |
| `llmModel` | `firebreak` | Primary Ollama / OpenAI-compat model |
| `llmBaseModel` | `qwen2.5:7b` | Fallback / base weights |
| `llmBaseUrl` | `http://ollama:11434/v1` | OpenAI-compat endpoint (**required** for scaffold health) |
| `edition` | `community` | `community` \| `pro` |
| `managedHosting` | `false` | Enable control-plane heartbeat hooks |
| `controlPlaneUrl` | `""` | `FIREBREAK_CONTROL_PLANE_URL` |
| `auditEs` | `false` | Mirror audit events to Elasticsearch |
| `auth0.enabled` | `false` | Wire Auth0 secret refs |
| `scaffoldExtra.baseUrl` | `""` | Optional third paid / remote scaffold |

Auth0: create secret `firebreak-auth0` with keys `domain`, `clientId`, `clientSecret`, `secret`, then set `firebreak.auth0.enabled=true`.

## Notes

- App results use **SQLite** on the output PVC (not Postgres).
- Point `firebreak.llmBaseUrl` at a reachable Ollama or vLLM service in-cluster.
- Full API list: `docs/api_reference.md` (Firebreak section).
