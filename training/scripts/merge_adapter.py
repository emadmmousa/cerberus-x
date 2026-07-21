#!/usr/bin/env python3
"""Merge a Firebreak QLoRA PEFT adapter into the base HF model (GPU/CPU host).

Writes training/adapters/firebreak-merged/ ready for convert_hf_to_gguf.py.
Does not download models in CI when --dry-run (default).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADAPTER = ROOT / "training" / "adapters" / "firebreak-qlora"
DEFAULT_OUT = ROOT / "training" / "adapters" / "firebreak-merged"
DEFAULT_BASE = "Qwen/Qwen2.5-7B-Instruct"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-dir", type=Path, default=DEFAULT_ADAPTER)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    print(f"base={args.base}")
    print(f"adapter={args.adapter_dir} exists={args.adapter_dir.is_dir()}")
    print(f"out={args.out}")
    if args.dry_run:
        print(
            "dry-run — on a host with the adapter + torch/peft:\n"
            f"  python {Path(__file__).name} --no-dry-run "
            f"--adapter-dir {args.adapter_dir} --out {args.out}\n"
            "  python training/scripts/export_gguf.py "
            f"--adapter-dir {args.adapter_dir} --merged-dir {args.out} --write-modelfile\n"
        )
        return 0

    if not args.adapter_dir.is_dir():
        print(f"missing adapter dir: {args.adapter_dir}", file=sys.stderr)
        return 1

    try:
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        print(f"missing deps: {exc}", file=sys.stderr)
        return 1

    tok = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base,
        torch_dtype="auto",
        device_map="cpu",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, str(args.adapter_dir))
    merged = model.merge_and_unload()
    args.out.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(args.out))
    tok.save_pretrained(str(args.out))
    print(f"merged weights written to {args.out}")
    print("Next: convert_hf_to_gguf.py → export_gguf.py --write-modelfile → ollama create")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
