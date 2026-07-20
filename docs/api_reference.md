# Cerberus‑X API Reference

## Authentication
All endpoints require an API key in `X-API-Key` header or OAuth2 Bearer token.

## Endpoints

### `POST /api/scan`
Start a scan.
- Body: `{"scan": "nmap", "target": "8.8.8.8", "ports": "80"}`

### `GET /api/status/{id}`
Get scan status.

### `POST /api/playbook/dynamic`
Run a dynamic playbook.
- Body: `{"session_id": "sess1", "playbook": "playbooks/aggressive.yaml", "context": {}}`

### `POST /api/aggressive/decide`
Get AI‑generated next steps.

### `POST /api/aggressive/execute`
Execute AI plan immediately.

### `POST /api/deception/spawn`
Deploy a honeypot.
- Body: `{"service": "http", "port": 8080}`

### `POST /api/report/generate`
Generate report from session.

## Rate Limits
Default: 100 req/min per IP. Adjusts dynamically based on threat level.

## WAF
The WAF inspects all requests and blocks SQLi, XSS, path traversal.