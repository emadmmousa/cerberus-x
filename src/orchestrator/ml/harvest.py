from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
HARVESTED_KEY = "firebreak:ml:harvested"
TERMINAL = frozenset({"SUCCESS", "FAILURE", "STOPPED", "REVOKED"})


def _output_dir() -> Path:
    return Path(
        os.environ.get("FIREBREAK_OUTPUT_DIR")
        or (Path(__file__).resolve().parents[3] / "output")
    )


def _already(job_id: str) -> bool:
    r = None
    try:
        from utils.redis_utils import get_redis

        r = get_redis()
        members = r.smembers(HARVESTED_KEY) or set()
        return job_id in members or job_id.encode() in members
    except Exception:
        return False


def _mark(job_id: str) -> None:
    try:
        from utils.redis_utils import get_redis

        get_redis().sadd(HARVESTED_KEY, job_id)
    except Exception as exc:
        logger.debug("harvest mark skipped: %s", exc)


def _record_from_job(job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    from orchestrator.ai.posture import DEFAULT_POSTURE
    from orchestrator.dataset.pipeline import normalize_record

    posture = job.get("posture") or (job.get("ai") or {}).get("posture") or DEFAULT_POSTURE
    target = job.get("target") or ""
    goal = job.get("nl_goal") or (job.get("ai") or {}).get("goal") or ""
    phases = list((job.get("results") or {}).keys())
    prompt = (
        f"Authorized mission on {target}. Posture={posture}. "
        f"Goal={goal}. completed_phases={phases}. Summarize planner outcome as JSON."
    )
    response = json.dumps(
        {
            "phase_name": phases[-1] if phases else "ai_done",
            "reason": f"Harvested completed mission {job_id}",
            "parallel": False,
            "stop": True,
            "tools": [],
            "mission_id": job_id,
            "state": job.get("state"),
        }
    )
    return normalize_record(
        {
            "source": "mission_harvest",
            "prompt": prompt,
            "response": response,
            "posture": posture,
            "license": "Apache-2.0",
            "mission_id": job_id,
        }
    )


def run_learning_tick() -> dict[str, Any]:
    from orchestrator.job_store import playbook_jobs

    out_path = _output_dir() / "dataset" / "harvest.jsonl"
    harvested = 0
    skipped_dup = 0
    try:
        summaries = playbook_jobs.list_summaries(limit=200)
        for summary in summaries:
            job_id = str(summary.get("task_id") or "")
            if not job_id:
                continue
            try:
                job = playbook_jobs[job_id]
            except KeyError:
                continue
            state = str(job.get("state") or "").upper()
            if state not in TERMINAL:
                continue
            if _already(job_id):
                skipped_dup += 1
                continue
            rec = _record_from_job(job_id, job)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            _mark(job_id)
            harvested += 1
    except Exception as exc:
        logger.exception("harvest failed")
        return {"error": str(exc), "harvested": harvested}

    health = []
    refreshed = False
    try:
        from orchestrator.ai.scaffolds import health_all

        health = health_all()
        refreshed = True
    except Exception as exc:
        logger.debug("scaffold refresh skipped: %s", exc)

    if harvested:
        try:
            from security.audit import audit_log

            audit_log("LEARNING_TICK", {"harvested": harvested, "path": str(out_path)})
        except Exception:
            pass

    return {
        "harvested": harvested,
        "skipped_dup": skipped_dup,
        "refreshed": refreshed,
        "health_count": len(health),
        "path": str(out_path),
    }
