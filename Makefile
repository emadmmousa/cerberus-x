# Firebreak / Firebreak developer targets
.PHONY: help test test-firebreak eval-report merge-posture merge-posture-apply \
	publish-dry-run publish-checklist publish-upload train-checklist \
	lab-seed frontend-test frontend-build

PYTHON ?= $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
PYTEST ?= $(PYTHON) -m pytest
REPO ?= firebreak/firebreak-v0
export PYTHONPATH := src

help:
	@echo "make test              — core unit tests (CI subset + Firebreak)"
	@echo "make test-firebreak    — Firebreak / Wave 1–5 focused suite"
	@echo "make eval-report       — offline honest eval → training/eval/REPORT.*"
	@echo "make lab-seed          — append authorized lab planner seeds"
	@echo "make merge-posture     — dry-run posture seed merge"
	@echo "make merge-posture-apply — write posture_merged.jsonl + v0 copies"
	@echo "make publish-dry-run   — validate dataset/v0 JSONL (no HF upload)"
	@echo "make publish-checklist — HF operator checklist"
	@echo "make publish-upload REPO=org/name — upload (needs HF_TOKEN)"
	@echo "make train-checklist   — QLoRA→GGUF preflight (see training/QLORA_GGUF.md)"
	@echo "make frontend-test     — SPA unit tests"
	@echo "make frontend-build    — build SPA into orchestrator/static/app"

test:
	$(PYTEST) -q \
	  tests/unit \
	  tests/test_ai_planner.py \
	  tests/test_ai_runner.py \
	  tests/test_decision_engine.py \
	  tests/test_ai_lab_api.py \
	  tests/test_ai_lab_consensus.py \
	  tests/test_router_cost.py \
	  tests/test_marketplace_heartbeat.py \
	  tests/test_blackboard.py \
	  tests/test_posture.py \
	  tests/test_dataset_rbac.py \
	  tests/test_pro_packaging.py \
	  tests/test_wave45_enterprise.py

test-firebreak:
	$(PYTEST) -q \
	  tests/test_ai_lab_api.py \
	  tests/test_ai_lab_consensus.py \
	  tests/test_router_cost.py \
	  tests/test_marketplace_heartbeat.py \
	  tests/test_scaffolds.py \
	  tests/test_blackboard.py \
	  tests/test_posture.py \
	  tests/test_prompt_guard.py \
	  tests/test_dataset_rbac.py \
	  tests/test_merge_contributions.py \
	  tests/test_merge_posture_seeds.py \
	  tests/test_training_export_scripts.py \
	  tests/test_publish_and_lab_seed.py \
	  tests/test_rbac_missions.py \
	  tests/test_pro_packaging.py \
	  tests/test_wave45_enterprise.py \
	  tests/test_playbook_catalog.py

eval-report:
	$(PYTHON) training/scripts/eval_report.py

lab-seed:
	$(PYTHON) training/scripts/generate_lab_seed.py

merge-posture:
	$(PYTHON) training/scripts/merge_posture_seeds.py

merge-posture-apply:
	$(PYTHON) training/scripts/merge_posture_seeds.py --apply

publish-dry-run:
	$(PYTHON) training/scripts/publish_dataset.py

publish-checklist:
	$(PYTHON) training/scripts/publish_dataset.py --checklist

publish-upload:
	$(PYTHON) training/scripts/publish_dataset.py --upload --repo $(REPO)

train-checklist:
	@echo "=== QLoRA → GGUF preflight ==="
	@$(PYTHON) training/scripts/qlora_train.py --include-posture --include-community
	@$(PYTHON) training/scripts/merge_adapter.py
	@$(PYTHON) training/scripts/export_gguf.py --write-modelfile
	@$(PYTHON) training/scripts/eval_report.py
	@echo "See training/QLORA_GGUF.md for GPU host steps."

frontend-test:
	cd frontend && npm test -- --run

frontend-build:
	cd frontend && npm run build
