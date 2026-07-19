## Final review fixes — 2026-07-19

- Session correlation now snapshots sessions before a Metasploit module runs and reports only newly created session IDs, filtering target metadata when present.
- A job that remains active past the polling deadline returns `code: "job_timeout"` with a clear error instead of a no-impact result.
- Post-exploitation modules return `status: "completed"` only after the job completes; retained sessions no longer set `vulnerable` or establish post-ex success.
- Added regression coverage for pre-existing same-host sessions, a persistent job timeout, completed post modules, and summary classification.

Verification:

- `pytest tests/test_metasploit_wrapper.py tests/test_decision_engine.py` — 38 passed
- `npm test -- --run src/__tests__/summarizeFinding.test.ts` — 20 passed
- `pytest -q` — 185 passed

## Post-ex attempted status — 2026-07-19

- Post modules now emit `status: "attempted"` after a clean job wait; `completed` is reserved for an explicit RPC success signal (none wired today).
- Summarizer maps `attempted` post results to `partial` / Needs attention; mission rollup no longer increments `postExSucceeded` without confirmed outcome.
- Exploit/auxiliary modules unchanged (`completed` / timeout / failed as before).

Verification:

- `pytest tests/test_metasploit_wrapper.py` — 26 passed
- `npm test -- --run src/__tests__/summarizeFinding.test.ts` — 21 passed
- `pytest -q` — 185 passed
