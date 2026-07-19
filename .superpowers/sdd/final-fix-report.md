## Final review fixes — 2026-07-19

- Session correlation now snapshots sessions before a Metasploit module runs and reports only newly created session IDs, filtering target metadata when present.
- A job that remains active past the polling deadline returns `code: "job_timeout"` with a clear error instead of a no-impact result.
- Post-exploitation modules return `status: "completed"` only after the job completes; retained sessions no longer set `vulnerable` or establish post-ex success.
- Added regression coverage for pre-existing same-host sessions, a persistent job timeout, completed post modules, and summary classification.

Verification:

- `pytest tests/test_metasploit_wrapper.py tests/test_decision_engine.py` — 38 passed
- `npm test -- --run src/__tests__/summarizeFinding.test.ts` — 20 passed
- `pytest -q` — 185 passed
