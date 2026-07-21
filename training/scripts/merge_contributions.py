#!/usr/bin/env python3
"""Merge community contributions into Firebreak SFT seed (Wave 3 → W2).

Reads training/dataset/v0/contributions.jsonl (+ optional output/dataset),
converts prompt/response pairs into planner-style chat messages, and appends
unique rows into training/seed/planner_examples.jsonl (or a sidecar file).

Default is dry-run: prints counts, writes nothing unless --apply.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.dataset.pipeline import accept_contribution  # noqa: E402

SEED = ROOT / "training" / "seed" / "planner_examples.jsonl"
CONTRIB_PATHS = [
    ROOT / "training" / "dataset" / "v0" / "contributions.jsonl",
    ROOT / "output" / "dataset" / "contributions.jsonl",
]
OUT_DEFAULT = ROOT / "training" / "seed" / "community_merged.jsonl"


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def contribution_to_messages(rec: dict) -> dict:
    """Map a community row to the seed chat format used by QLoRA."""
    posture = rec.get("posture") or "balanced"
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    f"Firebreak planner (posture={posture}). "
                    "Reply with JSON only when asked for a plan. "
                    "Authorized engagements only; wrappers-only."
                ),
            },
            {"role": "user", "content": rec["prompt"]},
            {"role": "assistant", "content": rec["response"]},
        ],
        "meta": {
            "source": rec.get("source") or "community",
            "license": rec.get("license") or "CC-BY-4.0",
            "posture": posture,
            "id": rec.get("id"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write merged sidecar")
    parser.add_argument(
        "--into-seed",
        action="store_true",
        help="Also append unique rows into planner_examples.jsonl",
    )
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    raw: list[dict] = []
    seen_ids: set[str] = set()
    for path in CONTRIB_PATHS:
        for row in _load_jsonl(path):
            try:
                norm = accept_contribution(row)
            except ValueError:
                continue
            cid = norm.get("id") or ""
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            raw.append(norm)

    print(f"unique contributions: {len(raw)}")
    if not raw:
        print("nothing to merge")
        return 0

    messages_rows = [contribution_to_messages(r) for r in raw]
    existing_seed = _load_jsonl(SEED)
    existing_assistant = {
        (m.get("messages") or [{}])[-1].get("content")
        for m in existing_seed
        if m.get("messages")
    }
    new_only = [
        r
        for r in messages_rows
        if (r.get("messages") or [{}])[-1].get("content") not in existing_assistant
    ]
    print(f"new vs seed: {len(new_only)} / {len(messages_rows)}")

    if not args.apply and not args.into_seed:
        print("dry-run only — pass --apply to write", args.out)
        return 0

    if args.apply:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            for row in messages_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {args.out} ({len(messages_rows)} rows)")

    if args.into_seed and new_only:
        SEED.parent.mkdir(parents=True, exist_ok=True)
        with SEED.open("a", encoding="utf-8") as fh:
            for row in new_only:
                # Keep seed rows without meta for schema eval compatibility.
                fh.write(
                    json.dumps({"messages": row["messages"]}, ensure_ascii=False)
                    + "\n"
                )
        print(f"appended {len(new_only)} rows to {SEED}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
