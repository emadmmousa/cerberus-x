# Firebreak training data (Firebreak own model)

This tree holds **seed** and future fine-tune data for `firebreak`.

## Layout

| Path | Purpose |
|------|---------|
| `seed/planner_examples.jsonl` | Few-shot / SFT examples: user mission JSON → planner JSON |
| `seed/aggressive_examples.jsonl` | 100 authorized aggressive contribute/SFT pairs |
| `seed/defensive_examples.jsonl` | 100 authorized defensive contribute/SFT pairs |
| `seed/balanced_examples.jsonl` | 50 authorized balanced contribute/SFT pairs |
| `seed/posture_merged.jsonl` | Chat-format merge of posture seeds (via merge script) |
| `eval/security_qa.jsonl` | Internal security Q&A checklist |
| `eval/REPORT.md` | Honest offline eval (no CSI claims) |
| `dataset/DATASET_CARD.md` | Hugging Face–style card for v0 |
| `dataset/v0/contributions.jsonl` | Community CC-BY contributions from Mission Control |
| `scripts/generate_seed.py` | Regenerates seed from `tools.inventory` allowlist |
| `scripts/generate_aggressive_examples.py` | Regenerates 100 aggressive examples |
| `scripts/generate_defensive_examples.py` | Regenerates 100 defensive examples |
| `scripts/generate_balanced_examples.py` | Regenerates 50 balanced examples |
| `scripts/merge_contributions.py` | Merge community contributions → seed / sidecar |
| `scripts/merge_posture_seeds.py` | Merge posture seeds → SFT + `dataset/v0` copies |
| `scripts/merge_adapter.py` | Merge QLoRA PEFT adapter → HF weights |
| `scripts/qlora_train.py` | Dry-run / GPU host recipe |
| `scripts/export_gguf.py` | GGUF Modelfile writer + Ollama recipe |
| `scripts/eval_planner_schema.py` | Schema validation over seed |
| `scripts/eval_security_qa.py` | Offline QA checklist sanity |
| `scripts/eval_report.py` | Combined honest internal report |
| `scripts/publish_dataset.py` | Dry-run / checklist / HF upload |
| `scripts/generate_lab_seed.py` | Authorized Juice/DVWA/lab planner seeds |
| `QLORA_GGUF.md` | GPU QLoRA → GGUF operator runbook |
| `HF_PUBLISH.md` | Hugging Face publish checklist |
| `README.md` | This file |

## License

Training examples committed here are Apache-2.0 with the project. Community
contributions via Mission Control default to **CC-BY-4.0**. Do not add
proprietary CSI/CAI datasets or customer engagement dumps.

## Contribute → train loop (Wave 3 → W2)

1. In Mission Control Options → Firebreak → **Dataset contribute** (filter by posture, or load an example).
2. Rows land in `output/dataset/contributions.jsonl` and `training/dataset/v0/`.
3. Merge community contributions:

```bash
python training/scripts/merge_contributions.py          # dry-run
python training/scripts/merge_contributions.py --apply  # write community_merged.jsonl
python training/scripts/merge_contributions.py --apply --into-seed  # append unique to seed
```

4. Merge dual-posture seed packs (100 aggressive + 100 defensive):

```bash
python training/scripts/generate_aggressive_examples.py
python training/scripts/generate_defensive_examples.py
python training/scripts/generate_balanced_examples.py
python training/scripts/merge_posture_seeds.py                 # dry-run
python training/scripts/merge_posture_seeds.py --apply         # posture_merged.jsonl + v0 copies
python training/scripts/merge_posture_seeds.py --apply --into-seed  # also append planner-JSON rows
```

5. Optional authorized lab seeds: `make lab-seed` (or `python training/scripts/generate_lab_seed.py`)
6. Re-run eval: `make eval-report`
7. On a GPU host — follow `training/QLORA_GGUF.md` (or `make train-checklist` for dry-run preflight):
```bash
python training/scripts/qlora_train.py --no-dry-run --include-posture
python training/scripts/merge_adapter.py --no-dry-run
# convert_hf_to_gguf.py … then:
python training/scripts/export_gguf.py --write-modelfile
```
8. HF publish: `make publish-checklist` then `make publish-upload` (needs `HF_TOKEN`) — see `training/HF_PUBLISH.md`.

## Honesty bounds

- No scraped criminal exploit PoC training.
- No “beats CSI” claims without public CAIBench (or equivalent) numbers.
- Eval report (`eval/REPORT.md`) records these as explicit `false` claims.

## Fine-tune path (Wave 2)

1. Grow `seed/*.jsonl` (and later `synthetic/`).
2. QLoRA on Qwen2.5-7B / Mistral-7B.
3. Export GGUF and `ollama create firebreak`.
4. Point `FIREBREAK_LLM_MODEL=firebreak`.

Until fine-tune lands, Ollama builds `firebreak` from `docker/ollama/Modelfile` (SYSTEM + base weights).
