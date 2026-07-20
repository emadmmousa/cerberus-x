# Cerberus‑X User Manual

## Overview
Cerberus‑X is an aggressive, AI‑driven security testing platform. It orchestrates 100+ tools, adapts in real‑time, and hunts for vulnerabilities with offensive precision.

## Quick Start
1. Clone the repo.
2. Run `docker-compose -f docker/docker-compose.yml up -d`.
3. Access dashboard at `http://localhost:5000`.
4. Authenticate via Google/GitHub or LDAP.

## Using the Dashboard
- **Scan**: Select tool, target, and options.
- **Playbooks**: Upload YAML playbooks to chain attacks.
- **AI Mode**: Enable AI decision engine to auto‑suggest next steps.
- **Honeypots**: Deploy decoys to profile attackers.

## Aggressive Features
- **Dynamic Rate Limiting**: Adjusts based on threat intelligence.
- **WAF Evasion Detection**: Blocks SQLi, XSS, etc., and logs attempts.
- **Immutable Audit**: All actions logged to S3 with object lock.
- **Auto‑Scaling**: Workers scale based on queue depth.

## Reporting
Generate executive summaries via the `/api/report/generate` endpoint.

## Troubleshooting
See logs: `docker-compose -f docker/docker-compose.yml logs -f`.