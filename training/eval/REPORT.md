# Firebreak internal eval report

Generated: `2026-07-21T01:45:38.839776+00:00`

## Honest positioning

- **Does not** claim to beat CSI / alias2-mini.
- **Does not** train on scraped criminal exploit PoCs.
- Offline CI checks only (schema, security Q&A, prompt-guard, posture, consensus, seed inventory).
- Live LLM quality is measured separately after QLoRA GGUF lands.

**Overall:** PASS

## Results

| Check | Status | Detail |
|-------|--------|--------|
| Planner schema | ok | 49/49 rows |
| Security Q&A | ok | 25/25 |
| Prompt guard | ok | injection surface reduced |
| Posture filter | ok | defensive drops offense tools |
| Consensus | ok | agreement + pick_best |
| Seed inventory | ok | planner=49 posture_merged=250 |

## Safety invariant

Tools execute only via Firebreak Celery wrappers (`_TASK_MAP`). Alias CAI unmanaged shell remains cancelled.

## Operator docs

- `training/QLORA_GGUF.md` — GPU train → GGUF
- `training/HF_PUBLISH.md` — Hugging Face upload checklist
