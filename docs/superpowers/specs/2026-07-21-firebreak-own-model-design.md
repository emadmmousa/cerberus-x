# Firebreak Own Model — Design (Wave 0 + Wave 2 start)

**Date:** 2026-07-21  
**Status:** Implementing  
**Replaces:** Alias CAI integration

## Goal

Ship **Firebreak’s own** cybersecurity LLM path:

1. Open Apache-2.0 project foundation  
2. Authorized Ollama model **`firebreak`** (base + SYSTEM for mission planning)  
3. Training/data scaffolding to fine-tune later (QLoRA → GGUF)  
4. Blackboard v0 (Redis) for Wave 1 multi-scaffold prep  

## Non-goals (this slice)

- Alias CAI / `alias1` / `CAI_LICENSE_OFF`  
- Full QLoRA training run in CI (GPU)  
- Multi-scaffold consensus UI  

## Model naming

| Env | Default | Role |
|-----|---------|------|
| `FIREBREAK_LLM_BASE_MODEL` | `qwen2.5:7b` | Open base weights via Ollama |
| `FIREBREAK_LLM_MODEL` | `firebreak` | Custom model built from Modelfile |

Operators may still point Instant cloud via env override.

## Deliverables

- Apache-2.0 `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`  
- `docker/ollama/Modelfile` — authorized Firebreak planner persona  
- `training/` — seed JSONL + generator from tool inventory  
- `src/orchestrator/ai/blackboard.py` + tests  
- Compose / `.env.example` defaults to `firebreak`  

## Success

- `ollama-pull` builds `firebreak` from Modelfile  
- Planner still works with heuristic fallback if Ollama down  
- Blackboard set/get/cas works against Redis  
- No CAI compose service  
