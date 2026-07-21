from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _output_dir() -> Path:
    return Path(os.environ.get("CERBERUS_OUTPUT_DIR") or (_repo_root() / "output"))


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").lower() in {"1", "true", "yes", "on"}


def _run_script(rel: str, extra_argv: list[str] | None = None) -> dict[str, Any]:
    script = _repo_root() / rel
    if not script.is_file():
        return {"ok": False, "error": f"missing {rel}"}
    cmd = [sys.executable, str(script)]
    if extra_argv:
        cmd.extend(extra_argv)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONPATH": str(_repo_root() / "src")},
        )
        out = (proc.stdout or "").strip().splitlines()
        parsed = None
        if out:
            try:
                parsed = json.loads(out[-1])
            except json.JSONDecodeError:
                parsed = {"raw": out[-1][:500]}
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "result": parsed,
            "stderr": (proc.stderr or "")[:500],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def run_daily_pipeline() -> dict[str, Any]:
    steps: dict[str, Any] = {}
    merge = _repo_root() / "training" / "scripts" / "merge_posture_seeds.py"
    if merge.is_file():
        steps["merge_posture"] = _run_script("training/scripts/merge_posture_seeds.py")
    contrib = _repo_root() / "training" / "scripts" / "merge_contributions.py"
    if contrib.is_file():
        steps["merge_contributions"] = _run_script(
            "training/scripts/merge_contributions.py"
        )

    steps["schema_eval"] = _run_script("training/scripts/eval_planner_schema.py")
    steps["security_qa"] = _run_script("training/scripts/eval_security_qa.py")

    gpu = _env_truthy("CERBERUS_TRAIN_GPU")
    steps["qlora"] = {
        "gpu_train": gpu,
        "mode": "real" if gpu else "dry_run",
    }
    if gpu:
        steps["qlora"]["result"] = _run_script(
            "training/scripts/qlora_train.py",
            ["--no-dry-run", "--include-posture", "--include-community"],
        )
    else:
        qlora = _repo_root() / "training" / "scripts" / "qlora_train.py"
        if qlora.is_file():
            try:
                proc = subprocess.run(
                    [sys.executable, str(qlora), "--dry-run"],
                    cwd=str(_repo_root()),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PYTHONPATH": str(_repo_root() / "src")},
                )
                steps["qlora"]["returncode"] = proc.returncode
                steps["qlora"]["stdout"] = (proc.stdout or "")[:300]
                if proc.returncode != 0 and "unrecognized arguments" in (
                    proc.stderr or ""
                ):
                    steps["qlora"]["mode"] = "skipped_no_dry_run"
            except Exception as exc:
                steps["qlora"]["error"] = str(exc)
                steps["qlora"]["mode"] = "skipped_no_dry_run"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "gpu_train": gpu,
    }
    out = _output_dir() / "ml"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "daily_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = out / "daily_report.md"
    md.write_text(
        f"# Daily ML report\n\nGenerated: {report['generated_at']}\n\n"
        f"GPU train: {gpu}\n\nSteps: {', '.join(steps.keys())}\n",
        encoding="utf-8",
    )
    try:
        from security.audit import audit_log

        audit_log("AUTO_TRAIN_DAILY", {"path": str(path), "gpu_train": gpu})
    except Exception:
        pass
    return {"ok": True, "gpu_train": gpu, "path": str(path), "steps": steps}
