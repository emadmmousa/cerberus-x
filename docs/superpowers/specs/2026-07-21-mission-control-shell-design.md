# Mission Control shell (SSO-first) — design

## Summary

Greenfield multi-route SPA for Firebreak Mission Control with Flask
controller blueprints, org-scoped missions, and session RBAC. No local user
directory in this slice — identity from Auth0 SSO or local admin login.

## Routes

| Path | Role |
|------|------|
| `/login` | public — local form + Auth0 `/auth/sso` |
| `/missions` | viewer+ |
| `/missions/new` | operator+ |
| `/missions/:id` | viewer+ |
| `/firebreak` | operator+ |
| `/admin` | viewer+ (self); admin for marketplace/heartbeat |

## Backend

- Controllers: `src/orchestrator/api/*`
- Services: `src/orchestrator/services/{missions,results,blackboard}.py`
- AuthZ: `security.rbac` — `require_role`, `assert_job_org`, `me_payload`
- Auth0 interactive login moved to `/auth/sso` so SPA owns `/login`

## Enforce

`FIREBREAK_RBAC_ENFORCE=true` requires authenticated session and role ranks.
`X-Firebreak-Role` ignored unless `FIREBREAK_SERVICE_ROLE_HEADER=true`.
