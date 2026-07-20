# Cerberus‑X Developer Guide

## Architecture
- **Orchestrator**: Flask + Socket.IO, API façade.
- **Workers**: Celery tasks for tools.
- **Tools**: Wrappers for 100+ scanners (add new ones in `src/tools/`).
- **Playbooks**: YAML definitions with conditionals and loops.
- **AI**: Ollama integration for decision making.
- **Storage**: Redis for state, Postgres for results, S3 for audit logs.

## Adding a New Tool
1. Create a class in `src/tools/` with `run()` and `parse_output()`.
2. Register it in `src/tools/__init__.py`.
3. Update the playbook schema.

## Aggressive Extensions
- **Honeypots**: Add new images in `docker/honeypots/`.
- **AI Decisions**: Modify the prompt in `ai_decision.py`.
- **Chaos Tests**: Add new tests in `tests/chaos/`.

## CI/CD
The `.github/workflows/ci.yml` runs SAST, SCA, container scanning, and unit/integration tests. Fails on high‑severity findings.

## Deployment
- Local: `docker-compose -f docker/docker-compose.yml up -d`
- Production: `helm install cerberus-x ./helm`

## Security
- All secrets managed by Vault.
- OAuth2/LDAP with adaptive MFA.
- Immutable audit logs.