#!/usr/bin/env python3
"""Prepare / publish Firebreak dataset v0 (Wave 3.1).

Default is dry-run: validates JSONL + prints Hugging Face upload commands.
Does not push unless --upload and huggingface_hub + credentials are available.

Never claims CSI parity. Rejects upload if DATASET_CARD claims competitive wins.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V0 = ROOT / "training" / "dataset" / "v0"
CARD = ROOT / "training" / "dataset" / "DATASET_CARD.md"
VERSION = "v0.1.1"

BANNED_CLAIM_PHRASES = (
    "beats csi",
    "better than csi",
    "beats alias2",
    "better than alias2",
    "surpasses csi",
)


def validate_jsonl(path: Path) -> int:
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            json.loads(line)
            n += 1
    return n


def card_is_honest(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "DATASET_CARD.md missing"
    text = path.read_text(encoding="utf-8").lower()
    for phrase in BANNED_CLAIM_PHRASES:
        if phrase in text:
            return False, f"card contains forbidden competitive claim: {phrase!r}"
    return True, "ok"


def print_checklist(total: int, files: list[Path]) -> None:
    print("=== Firebreak HF publish checklist ===")
    print(f"version: {VERSION}")
    print(f"rows: {total} across {len(files)} files")
    for path in files:
        print(f"  - {path.name}")
    print("card:", CARD if CARD.exists() else "MISSING")
    print("auth: HF_TOKEN set =" , bool(os.environ.get("HF_TOKEN")))
    print("see: training/HF_PUBLISH.md")
    print("forbidden: scraped criminal PoCs; unbenchmarked CSI claims")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="firebreak/firebreak-v0")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument(
        "--checklist",
        action="store_true",
        help="Print operator checklist and exit (implies dry-run)",
    )
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args()

    files = sorted(V0.glob("*.jsonl"))
    if not files:
        print(f"no jsonl under {V0}", file=sys.stderr)
        return 1
    total = 0
    for path in files:
        n = validate_jsonl(path)
        total += n
        print(f"  {path.name}: {n} rows")
    print(f"Dataset {VERSION}: {total} rows across {len(files)} files")
    print(f"Card: {CARD if CARD.exists() else 'missing'}")

    ok_card, card_msg = card_is_honest(CARD)
    if not ok_card:
        print(f"card check failed: {card_msg}", file=sys.stderr)
        return 1
    print(f"card honesty: {card_msg}")

    if args.checklist:
        print_checklist(total, files)
        return 0

    print(
        "\nHugging Face (manual):\n"
        f"  huggingface-cli upload {args.repo} {V0} --repo-type dataset\n"
        f"  # include {CARD.name} as README.md in the dataset repo\n"
        "  # see training/HF_PUBLISH.md\n"
    )
    if args.upload:
        if not (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")):
            print(
                "HF_TOKEN / HUGGING_FACE_HUB_TOKEN not set — "
                "run huggingface-cli login or export a write token",
                file=sys.stderr,
            )
            return 1
        try:
            from huggingface_hub import HfApi  # type: ignore
        except ImportError:
            print("huggingface_hub not installed", file=sys.stderr)
            return 1
        api = HfApi()
        api.upload_folder(
            folder_path=str(V0),
            repo_id=args.repo,
            repo_type="dataset",
        )
        if CARD.exists():
            api.upload_file(
                path_or_fileobj=str(CARD),
                path_in_repo="README.md",
                repo_id=args.repo,
                repo_type="dataset",
            )
        print(f"Uploaded to {args.repo}")
    else:
        print("dry-run only — no upload")
    stamp = V0 / "VERSION"
    stamp.write_text(VERSION + "\n", encoding="utf-8")
    print(f"Wrote {stamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
