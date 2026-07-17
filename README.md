# Cerberus‑X
**Universal Offensive Orchestration Framework**  
Integrates 100+ security tools into a single AI‑driven kill chain.

## Status
🚧 **Under active development** – Week 1: Skeleton & Core Wrappers.

## Architecture
- **Orchestrator** (Celery + Redis) – schedules and runs tasks in parallel.
- **Tool Wrappers** – standardized interface for every tool.
- **MCP Server** (NyxStrike) – AI decision layer.
- **Dashboard** (Flask) – real‑time monitoring and control.

## Quick Start
```bash
docker-compose up -d
python src/orchestrator/cli.py --target https://example.com --playbook playbooks/default.yaml