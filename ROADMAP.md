# Firebreak / Firebreak Roadmap

Public roadmap aligned with [PROJECT FIREBREAK](docs/superpowers/plans/2026-07-21-firebreak-upgrade-plan.md).

## Shipped

| Wave | Capability |
|------|------------|
| **W0** | Apache-2.0, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, ROADMAP, `firebreak` Modelfile |
| **W1** | Multi-scaffold, consensus, Blackboard UI, cost-route flag, Mission Control panel |
| **W2** | Training seed, QLoRA dry-run + real train path, GGUF export, schema + security QA eval |
| **W3** | Dataset pipeline, synthetic lab, HF card + publish script, contribute API/UI |
| **W4** | RBAC, OIDC login/callback, org-scoped results/Blackboard, Redis job HA, Helm |
| **W5** | Open-core edition flags + `/api/edition/status` + Helm Auth0 packaging |

## Next

- [x] Rebuild Ollama model after Modelfile prompt-injection rules
- [x] Auth0 env wired — SSO ready; Sign in via Mission Control
- [x] Multi-scaffold default enabled (dual Ollama firebreak + fallback)
- [x] W1.7 DecisionEngine → Blackboard `proposed_action`
- [x] Honest internal eval report (`training/scripts/eval_report.py`)
- [x] Dataset contribute examples + merge_contributions → seed path
- [x] Audit recent API + Mission Control audit strip (W4.4 visibility)
- [x] Dual-posture seed packs (100 aggressive + 100 defensive) + merge_posture_seeds
- [x] Contribute UI posture filter (`/api/dataset/examples?posture=`)
- [x] Balanced seed (50) + GGUF helpers (`merge_adapter.py`, `export_gguf --write-modelfile`)
- [x] Scaffold marketplace API + managed hosting heartbeat (W5 hooks)
- [x] Marketplace → live scaffolds + cost-route estimates
- [x] Helm LLM base URL / audit ES / control-plane env parity
- [x] Contribute posture → merge/train; Blackboard consensus strip
- [x] Mission Control marketplace register + cost display + hardening blob export
- [x] Compose/Helm EXTRA scaffold + worker Deployment; Makefile + CI Firebreak gates
- [x] Helm Redis/ES/MSF/PVC stubs; marketplace unregister; nested Compose Firebreak sync
- [x] User manual Firebreak UI; Helm README; MissionControl mocks; drop dead postgres Helm config
- [x] QLoRA→GGUF operator runbook (`training/QLORA_GGUF.md`) + `make train-checklist`
- [x] HF publish checklist (`training/HF_PUBLISH.md`) + safer `publish_dataset.py` (card honesty, `HF_TOKEN`)
- [x] Authorized lab planner seeds (`generate_lab_seed.py`) + expanded security QA + seed inventory in eval
- [x] Greenfield Mission Control shell (react-router: Login/Missions/Firebreak/Admin) + API controllers + SSO-first RBAC
- [ ] Run GPU QLoRA → GGUF replace of Modelfile-only weights (`--include-posture`) — operator GPU host
- [ ] `make publish-upload` to Hugging Face (dry-run/checklist OK) — needs `HF_TOKEN` + repo
- [ ] Point `FIREBREAK_CONTROL_PLANE_URL` at a real control plane when hosting Pro

## Dual posture (offense + defense)

| Posture | YAML playbook | Behavior |
|---------|---------------|----------|
| **balanced** (default) | `balanced_offense_defense.yaml` | Aggressive discovery + hardening recs |
| **aggressive** | `complete_dark_arsenal.yaml` | Full offense arsenal |
| **defensive** | `defensive_audit.yaml` | Exposure scanners only |

APIs: `GET /api/playbooks`, `GET /api/missions/<id>/hardening`, `GET /api/dataset/examples?posture=`.
UI posture select maps to playbook on launch; contribute UI can filter example packs.
AI missions return `ai.hardening[]` remediation bullets after completion.
Training: `training/seed/{aggressive,defensive}_examples.jsonl` → `posture_merged.jsonl`.
