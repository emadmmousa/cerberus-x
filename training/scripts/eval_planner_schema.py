#!/usr/bin/env python3
"""Lightweight planner JSON schema eval against seed assistants (Wave 2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.ai import llm  # noqa: E402

SEED = ROOT / "training" / "seed" / "planner_examples.jsonl"
REQUIRED = {"phase_name", "reason", "parallel", "stop", "tools"}


def main() -> int:
    ok = 0
    bad = 0
    with SEED.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            assistant = row["messages"][-1]["content"]
            parsed = llm.parse_json_object(assistant)
            if not parsed or not REQUIRED.issubset(parsed.keys()):
                # describe_tool / knowledge rows are not full plans
                if parsed and "tool" in parsed and "description" in parsed:
                    ok += 1
                    continue
                if parsed and "answer" in parsed:
                    ok += 1
                    continue
                bad += 1
                continue
            if not isinstance(parsed.get("tools"), list):
                bad += 1
                continue
            ok += 1
    total = ok + bad
    print(json.dumps({"ok": ok, "bad": bad, "total": total, "pass_rate": ok / total if total else 0}))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
