# Open-core (Firebreak Wave 5)

Firebreak is **Apache-2.0** and fully usable self-hosted in **community** edition.

## Editions

| Flag | Meaning |
|------|---------|
| `FIREBREAK_EDITION=community` (default) | All wrappers, Firebreak model, Blackboard, multi-scaffold |
| `FIREBREAK_EDITION=pro` | Same core + packaging hooks for SSO/RBAC/managed hosting |

Pro does **not** strip scanning capability from community. It only marks
enterprise packaging features (`security.edition.feature_flags()`).

## What we will not do

- Paywall the 23 Celery wrappers or Mission Control basic mission flow
- Depend on Alias CAI PRO for core planning
- Monetize before Waves 0–1 are proven by external users

## Future Pro packaging

Enable with `FIREBREAK_EDITION=pro` (optional `FIREBREAK_MANAGED_HOSTING=true`,
`FIREBREAK_CONTROL_PLANE_URL=…`).

| Endpoint | Purpose |
|----------|---------|
| `GET /api/edition/status` | SSO readiness + managed hosting hooks |
| `GET|POST /api/edition/heartbeat` | Control-plane heartbeat payload / ping |
| `GET|POST /api/scaffolds/marketplace` | Scaffold catalog; POST register is Pro-only (needs `base_url`) |
| `GET /api/ai-lab/status` → `sso` | Auth0/OIDC checklist (missing env names only) |

Registered marketplace scaffolds with a real `base_url` join the live multi-scaffold
router. Optional third env scaffold: `FIREBREAK_SCAFFOLD_EXTRA_*`. Cost routing:
`FIREBREAK_SCAFFOLD_COST_ROUTE=true` prefers lower `cost_per_1k`.

Pro does not strip scanning. Community keeps full arsenal + Firebreak model.
Community can **read** the scaffold marketplace catalog; registering custom
scaffolds requires Pro.
