# Firebreak Dataset Card (v0)

## Dataset Summary

Synthetic and inventory-derived examples for training / evaluating the
Firebreak planner. **Authorized lab use only** — no customer dumps.

## Files

| File | Description |
|------|-------------|
| `v0/synthetic_inventory.jsonl` | Tool describe Q&A from `tools.inventory` |
| `v0/aggressive_examples.jsonl` | 100 authorized aggressive planner/contribute pairs |
| `v0/defensive_examples.jsonl` | 100 authorized defensive exposure/hardening pairs |
| `v0/balanced_examples.jsonl` | 50 authorized balanced offense+defense pairs |
| `v0/contributions.jsonl` | Community CC-BY contributions |
| `../seed/planner_examples.jsonl` | Planner JSON SFT pairs |
| `../seed/posture_merged.jsonl` | Dual-posture chat-format SFT merge |
| `../eval/security_qa.jsonl` | Internal security Q&A checklist |

## Languages

English

## License

Apache-2.0 for code-generated inventory text. Prefer **CC-BY-4.0** for any
community contributions accepted via `/api/dataset/contribute` (stored with
`license` field).

## Personal data

Pipeline runs `redact_pii` (emails, RFC1918 IPs). Do not contribute real
engagement artifacts without scrubbing.

## Homepages / citation

Firebreak Firebreak — see `ROADMAP.md` and `training/README.md`.

## Intended use

Fine-tune and eval of authorized offensive-security **planning** assistants.
Not for generating weaponized exploits outside authorized testing.

## Non-goals / honesty

- Do **not** train on scraped criminal exploit PoCs.
- Do **not** claim this dataset or resulting models beat CSI / alias2-mini
  without measured public CAIBench (or equivalent) numbers.
- Community contributions must pass soft safety filters (no unmanaged shell teaching).

## Hugging Face

See `training/HF_PUBLISH.md`. Checklist: `make publish-checklist`. Upload:
`make publish-upload REPO=firebreak/firebreak-v0` (requires `HF_TOKEN`).
Uploads `training/dataset/v0/*.jsonl` and this card as `README.md`.
