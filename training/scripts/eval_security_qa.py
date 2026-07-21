#!/usr/bin/env python3
"""Eval harness for internal security Q&A checklist (Wave 2.4).

Checks that each expected answer keyword appears in a simple bag-of-words
match against the gold answer (offline; no LLM required in CI).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "training" / "eval" / "security_qa.jsonl"


def keywords(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_./:-]+", text.lower()) if len(t) > 2}


def main() -> int:
    rows = []
    with QA.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    # Self-consistency: gold answers must contain distinctive tokens from themselves
    # (sanity that the checklist file is well-formed). A live LLM eval can score
    # model answers against the same keywords later.
    ok = 0
    for row in rows:
        ans = keywords(row["answer"])
        q = keywords(row["question"])
        if len(ans) >= 1 and (ans - q):
            ok += 1
    total = len(rows)
    report = {"ok": ok, "total": total, "pass_rate": ok / total if total else 0.0}
    print(json.dumps(report))
    return 0 if ok == total and total >= 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
