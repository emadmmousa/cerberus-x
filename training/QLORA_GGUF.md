# Firebreak QLoRA → GGUF operator runbook

Authorized training only. Uses Firebreak seed + dual-posture examples.  
**Does not** scrape criminal exploit PoCs. **Does not** claim CSI / alias2-mini wins.

## Prerequisites

- CUDA GPU host (≈16GB+ VRAM for 7B QLoRA)
- Python 3.11+ with:

```bash
pip install transformers peft bitsandbytes datasets trl torch huggingface_hub
```

- Optional: [llama.cpp](https://github.com/ggerganov/llama.cpp) for GGUF conversion
- Optional: Ollama on the same host for `ollama create`

## One-command dry checklist (any machine)

```bash
make train-checklist
```

## GPU host steps

### 1. Validate seeds

```bash
make merge-posture-apply
make eval-report
python training/scripts/qlora_train.py --include-posture --include-community   # dry-run
```

### 2. Train QLoRA adapter

```bash
python training/scripts/qlora_train.py --no-dry-run --include-posture --include-community \
  --base Qwen/Qwen2.5-7B-Instruct \
  --out training/adapters/firebreak-qlora \
  --max-steps 200
```

### 3. Merge adapter → HF weights

```bash
python training/scripts/merge_adapter.py --no-dry-run \
  --adapter-dir training/adapters/firebreak-qlora \
  --out training/adapters/firebreak-merged
```

### 4. Convert to GGUF

```bash
# from a llama.cpp checkout:
python convert_hf_to_gguf.py /path/to/firebreak/training/adapters/firebreak-merged \
  --outfile /path/to/firebreak/training/adapters/firebreak-q4.gguf \
  --outtype q4_k_m
```

### 5. Write Ollama Modelfile + create model

```bash
python training/scripts/export_gguf.py --write-modelfile \
  --gguf training/adapters/firebreak-q4.gguf
cd training/adapters
ollama create firebreak -f Modelfile.firebreak-gguf
```

### 6. Point Firebreak at the fine-tuned model

```bash
# .env / compose
FIREBREAK_LLM_MODEL=firebreak
FIREBREAK_LLM_BASE_URL=http://ollama:11434/v1
```

Until GGUF lands, Compose still builds persona-only weights via:

```bash
docker compose run --rm ollama-pull
```

## Honest eval after train

```bash
make eval-report
# Live planner quality: run authorized lab missions; compare to heuristic baseline.
# Do not publish “beats CSI” until public CAIBench numbers exist.
```
