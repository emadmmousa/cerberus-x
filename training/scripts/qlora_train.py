#!/usr/bin/env python3
"""QLoRA fine-tune for firebreak (Wave 2).

Default: dry-run (validate seed + print recipe).
With --no-dry-run and transformers/peft/trl installed + CUDA: runs a short SFT.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "training" / "seed" / "planner_examples.jsonl"
POSTURE_MERGED = ROOT / "training" / "seed" / "posture_merged.jsonl"
COMMUNITY_MERGED = ROOT / "training" / "seed" / "community_merged.jsonl"


def validate_seed(path: Path) -> int:
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            assert "messages" in row
            n += 1
    return n


def load_messages(*paths: Path) -> list[dict]:
    rows = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                key = json.dumps(row.get("messages"), sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    return rows


def run_sft(seeds: list[Path], base: str, out_dir: Path, max_steps: int) -> None:
    # Heavy imports only when training for real.
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from trl import SFTTrainer

    rows = load_messages(*seeds)

    def to_text(example):
        parts = []
        for m in example["messages"]:
            parts.append(f"<|{m['role']}|>\n{m['content']}")
        return {"text": "\n".join(parts)}

    ds = Dataset.from_list(rows).map(to_text)
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        ),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(out_dir),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        max_steps=max_steps,
        logging_steps=1,
        save_steps=max(max_steps, 1),
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model,
        train_dataset=ds,
        args=args,
        processing_class=tokenizer,
        dataset_text_field="text",
        max_seq_length=2048,
    )
    trainer.train()
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    print(f"Adapter saved to {out_dir}")
    print("Next: merge + convert_hf_to_gguf.py → ollama create firebreak")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=SEED)
    parser.add_argument(
        "--include-posture",
        action="store_true",
        help=f"Also train on {POSTURE_MERGED.name} when present",
    )
    parser.add_argument(
        "--include-community",
        action="store_true",
        help=f"Also train on {COMMUNITY_MERGED.name} when present",
    )
    parser.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--out", type=Path, default=ROOT / "training" / "adapters" / "firebreak-qlora")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    if not args.seed.exists():
        print(f"missing seed: {args.seed}", file=sys.stderr)
        return 1
    seeds = [args.seed]
    if args.include_posture and POSTURE_MERGED.is_file():
        seeds.append(POSTURE_MERGED)
    if args.include_community and COMMUNITY_MERGED.is_file():
        seeds.append(COMMUNITY_MERGED)
    n = sum(validate_seed(p) for p in seeds)
    print(f"Validated {n} seed examples across {[str(p) for p in seeds]}")
    if args.dry_run:
        print(
            "Recommended (GPU host):\n"
            f"  pip install transformers peft bitsandbytes datasets trl torch\n"
            f"  python {Path(__file__).name} --no-dry-run --include-posture "
            f"--include-community --base {args.base} --out {args.out} "
            f"--max-steps {args.max_steps}\n"
            "  # then training/scripts/export_gguf.py --adapter-dir <out>\n"
        )
        print("dry-run only — no weights written")
        return 0
    try:
        import torch  # noqa: F401
        import peft  # noqa: F401
        import transformers  # noqa: F401
        import trl  # noqa: F401
    except ImportError as exc:
        print(f"missing training deps: {exc}", file=sys.stderr)
        return 1
    run_sft(seeds, args.base, args.out, args.max_steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
