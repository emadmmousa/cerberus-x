#!/usr/bin/env python3
"""Merge posture seed JSONL (aggressive/defensive/balanced) into SFT chat format.

Reads training/seed/{aggressive,defensive,balanced}_examples.jsonl, converts to the
planner chat schema used by QLoRA, writes:
  - training/seed/posture_merged.jsonl  (always with --apply)
  - optionally appends unique rows into planner_examples.jsonl (--into-seed)
  - copies raw contribute rows into training/dataset/v0/ for HF publish

Default is dry-run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.dataset.pipeline import accept_contribution  # noqa: E402

SEED = ROOT / "training" / "seed" / "planner_examples.jsonl"
POSTURE_PATHS = [
    ROOT / "training" / "seed" / "aggressive_examples.jsonl",
    ROOT / "training" / "seed" / "defensive_examples.jsonl",
    ROOT / "training" / "seed" / "balanced_examples.jsonl",
]
OUT_DEFAULT = ROOT / "training" / "seed" / "posture_merged.jsonl"
V0 = ROOT / "training" / "dataset" / "v0"


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
            "source": rec.get("source") or "posture_seed",
            "license": rec.get("license") or "Apache-2.0",
            "posture": posture,
            "id": rec.get("id"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write merged sidecar + v0 copies")
    parser.add_argument(
        "--into-seed",
        action="store_true",
        help="Also append unique rows into planner_examples.jsonl",
    )
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    raw: list[dict] = []
    seen_ids: set[str] = set()
    for path in POSTURE_PATHS:
        for row in _load_jsonl(path):
            try:
                # Reuse safety filter; keep Apache license + id/posture.
                norm = accept_contribution(
                    {
                        "prompt": row.get("prompt"),
                        "response": row.get("response"),
                        "license": row.get("license") or "Apache-2.0",
                        "contributor": row.get("source") or "posture_seed",
                    }
                )
            except ValueError as exc:
                print(f"skip {row.get('id')}: {exc}", file=sys.stderr)
                continue
            # Preserve stable seed ids (accept_contribution regenerates hash ids).
            if row.get("id"):
                norm["id"] = str(row["id"])
            if row.get("posture"):
                norm["posture"] = row["posture"]
            if row.get("source"):
                norm["source"] = row["source"]
            cid = norm["id"]
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            raw.append(norm)

    print(f"unique posture examples: {len(raw)}")
    if not raw:
        print("nothing to merge — run generate_*_examples.py first")
        return 1

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
    by_posture: dict[str, int] = {}
    for r in raw:
        p = str(r.get("posture") or "unknown")
        by_posture[p] = by_posture.get(p, 0) + 1
    print(f"by posture: {by_posture}")
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

        V0.mkdir(parents=True, exist_ok=True)
        for path in POSTURE_PATHS:
            if path.is_file():
                dest = V0 / path.name
                shutil.copy2(path, dest)
                print(f"copied {path.name} → {dest}")

    if args.into_seed and new_only:
        # Only append assistant rows that look like planner JSON (schema eval safe).
        REQUIRED = {"phase_name", "reason", "parallel", "stop", "tools"}
        plan_only = []
        for row in new_only:
            content = (row.get("messages") or [{}])[-1].get("content") or ""
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and REQUIRED.issubset(parsed.keys()):
                plan_only.append(row)
        SEED.parent.mkdir(parents=True, exist_ok=True)
        with SEED.open("a", encoding="utf-8") as fh:
            for row in plan_only:
                fh.write(
                    json.dumps({"messages": row["messages"]}, ensure_ascii=False)
                    + "\n"
                )
        print(
            f"appended {len(plan_only)} planner-JSON rows to {SEED} "
            f"(skipped {len(new_only) - len(plan_only)} free-text)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
