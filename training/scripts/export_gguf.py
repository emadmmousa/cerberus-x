#!/usr/bin/env python3
"""Export / document GGUF → Ollama path for firebreak (Wave 2.3).

Validates seed exists, optionally writes a Modelfile that FROM's a local GGUF
(or merged HF dir instructions). Does not download models in CI.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "training" / "seed" / "planner_examples.jsonl"
MODELFILE = ROOT / "docker" / "ollama" / "Modelfile"
OUT_MODELFILE = ROOT / "training" / "adapters" / "Modelfile.firebreak-gguf"


def _extract_system(modelfile: Path) -> str:
    text = modelfile.read_text(encoding="utf-8")
    m = re.search(r'SYSTEM\s+"""(.*?)"""', text, re.S)
    if not m:
        return "You are Firebreak, an authorized cybersecurity planner."
    return m.group(1).strip()


def write_modelfile(*, gguf: Path, out: Path, name: str) -> Path:
    system = _extract_system(MODELFILE) if MODELFILE.is_file() else "Firebreak planner."
    # Relative FROM works when ollama create is run from the adapters dir.
    from_line = gguf.name if gguf.parent.resolve() == out.parent.resolve() else str(gguf)
    body = (
        f"# Generated for {name} — do not hand-edit SYSTEM without syncing docker/ollama/Modelfile\n"
        f"FROM {from_line}\n"
        "\n"
        "PARAMETER temperature 0.3\n"
        "PARAMETER top_p 0.9\n"
        "PARAMETER top_k 40\n"
        "PARAMETER num_ctx 8192\n"
        'PARAMETER stop "<|im_end|>"\n'
        'PARAMETER stop "<|endoftext|>"\n'
        "\n"
        f'SYSTEM """\n{system}\n"""\n'
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-dir", type=Path, default=None, help="PEFT adapter path")
    parser.add_argument("--merged-dir", type=Path, default=None, help="Merged HF weights path")
    parser.add_argument(
        "--gguf",
        type=Path,
        default=ROOT / "training" / "adapters" / "firebreak-q4.gguf",
    )
    parser.add_argument("--out-name", default="firebreak")
    parser.add_argument(
        "--write-modelfile",
        action="store_true",
        help=f"Write {OUT_MODELFILE.name} with SYSTEM from docker/ollama/Modelfile",
    )
    parser.add_argument("--modelfile-out", type=Path, default=OUT_MODELFILE)
    args = parser.parse_args()

    if not SEED.exists():
        print(f"missing seed: {SEED}", file=sys.stderr)
        return 1

    print("=== Firebreak GGUF export (manual GPU host) ===")
    print(f"Seed: {SEED} ({sum(1 for _ in SEED.open() if _.strip())} lines)")
    print(f"Modelfile (SYSTEM source): {MODELFILE}")
    if args.adapter_dir:
        print(f"Adapter: {args.adapter_dir}")
    if args.merged_dir:
        print(f"Merged HF: {args.merged_dir}")
    print(f"Expected GGUF: {args.gguf}")

    if args.write_modelfile:
        path = write_modelfile(gguf=args.gguf, out=args.modelfile_out, name=args.out_name)
        print(f"Wrote {path}")

    print(
        "\nRecommended:\n"
        "  1. python training/scripts/qlora_train.py --no-dry-run --include-posture\n"
        "  2. python training/scripts/merge_adapter.py --no-dry-run\n"
        "  3. python llama.cpp/convert_hf_to_gguf.py training/adapters/firebreak-merged "
        f"--outfile {args.gguf} --outtype q4_k_m\n"
        f"  4. python training/scripts/export_gguf.py --write-modelfile --gguf {args.gguf}\n"
        f"  5. cd training/adapters && ollama create {args.out_name} -f {args.modelfile_out.name}\n"
        f"  6. FIREBREAK_LLM_MODEL={args.out_name}\n"
    )
    print("Until then: `docker compose run --rm ollama-pull` builds from Modelfile + base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
