# Contributing to Firebreak (Firebreak)

Thanks for helping build an **open**, auditable AI offensive-security platform for **authorized** engagements only.

## Ground rules

1. Only contribute code, data, and docs intended for **legal, authorized** security testing.
2. Do **not** submit jailbreak prompts, credential dumps, or live exploit PoCs aimed at unauthorized targets.
3. Prefer small PRs with tests.
4. Follow Conventional Commits (`feat:`, `fix:`, `docs:`, …).

## Setup

```bash
cp .env.example .env   # fill secrets locally — never commit .env
pip install -r requirements.txt -r requirements-dev.txt
make test-firebreak    # or: PYTHONPATH=src pytest -q
make frontend-test
```

Useful Make targets: `eval-report`, `merge-posture`, `publish-dry-run`, `frontend-build`.

## Adding a tool wrapper

1. Implement `scan()` under `src/tools/wrappers/`.
2. Register Celery task + `_TASK_MAP` in `src/orchestrator/tasks.py`.
3. Add catalog entry in `src/tools/inventory.py`.
4. Add tests under `tests/`.

## Own model / training data

- Seed data lives in `training/`.
- Do not commit secrets or customer engagement data.
- See `training/README.md`.

## Pull requests

- Describe *why*, link issues, note risk level for high-risk tools.
- CI must pass (unit + frontend vitest).
