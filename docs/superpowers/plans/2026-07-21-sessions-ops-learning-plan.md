# Sessions, Ops Toggles, Bulk Examples & Scheduled Learning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Redis-backed per-user sessions, Admin Ops toggles (Auto-Scale / Auto-Train / Learning Tick), FirebreakPanel bulk example load/submit, a daily merge+eval ML pipeline, and a per-minute mission harvest tick — all off by default.

**Architecture:** Runtime ops flags live in `admin_store` (Redis) with env deferral, resolved by `orchestrator.ml.flags.effective_*()`. Celery beat always registers cheap periodic tasks that no-op when Off. Flask-Session stores sessions in Redis when a real Redis client is available. Bulk examples stay frontend-only against existing dataset APIs.

**Tech Stack:** Flask 3, Flask-Session, Redis, Celery beat, React/Vitest, pytest

**Spec:** `docs/superpowers/specs/2026-07-21-sessions-ops-learning-design.md`

## Global Constraints

- All schedulers default **Off**; env defer path when Admin override is `null`.
- Effective resolution order: admin override → env → `false`.
- QLoRA stays dry-run unless `CERBERUS_TRAIN_GPU` is truthy.
- One-shot `POST /api/scale/auto` is **not** gated by Auto-Scale beat flag.
- No new dataset contribute API; reuse `GET/POST /api/dataset/*`.
- Conventional Commits for every commit step.
- Minimize drive-by refactors; touch only files listed per task.

## File map

| Path | Responsibility |
|------|----------------|
| `src/orchestrator/ml/__init__.py` | Package marker |
| `src/orchestrator/ml/flags.py` | `effective_auto_scale/train/learning_tick()` |
| `src/orchestrator/ml/harvest.py` | Per-minute mission harvest + scaffold refresh |
| `src/orchestrator/ml/auto_train.py` | Daily merge + eval + report |
| `src/orchestrator/session_config.py` | Flask-Session Redis setup helper |
| `src/security/admin_store.py` | Ops flag get/set/overrides |
| `src/orchestrator/api/admin.py` | `PUT /api/admin/settings/ops`; extend GET settings |
| `src/orchestrator/celery_app.py` | Register scale / learning / daily tasks |
| `src/orchestrator/dashboard.py` | Call session config on boot |
| `requirements.txt` | `Flask-Session` |
| `.env.example` | New env vars |
| `frontend/src/components/FirebreakPanel.tsx` | Load all / Submit all |
| `frontend/src/views/Admin.tsx` | Ops tab |
| `frontend/src/api/client.ts` | `setOpsSettings` + types |
| `tests/test_ops_flags.py` | Effective helpers + admin store |
| `tests/test_ml_harvest.py` | Harvest + skip gate |
| `tests/test_ml_auto_train.py` | Daily dry-run |
| `tests/test_session_config.py` | Session config smoke |
| `frontend/src/__tests__/FirebreakPanel.bulk.test.tsx` | Bulk UI |
| `frontend/src/__tests__/Admin.ops.test.tsx` | Ops tab |

---

### Task 1: Ops effective flags (`admin_store` + `ml.flags`)

**Files:**
- Create: `src/orchestrator/ml/__init__.py`
- Create: `src/orchestrator/ml/flags.py`
- Modify: `src/security/admin_store.py` (`get_settings`, add ops setters/overrides)
- Test: `tests/test_ops_flags.py`

**Interfaces:**
- Consumes: `admin_store` Redis settings pattern (`rbac_enforce` override)
- Produces:
  - `OPS_FLAGS = frozenset({"auto_scale", "auto_train", "learning_tick"})`
  - `admin_store.set_ops_flag(name: str, value: Optional[bool]) -> dict`
  - `admin_store.auto_scale_override() -> Optional[bool]` (and train / learning_tick)
  - `orchestrator.ml.flags.effective_auto_scale() -> bool`
  - `orchestrator.ml.flags.effective_auto_train() -> bool`
  - `orchestrator.ml.flags.effective_learning_tick() -> bool`
  - `orchestrator.ml.flags._env_truthy(name: str) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ops_flags.py
import os
import pytest


@pytest.fixture(autouse=True)
def _clean_admin_store(monkeypatch):
    from utils.redis_utils import get_redis
    from security import admin_store

    r = get_redis()
    try:
        r.delete(admin_store.SETTINGS_KEY)
    except Exception:
        pass
    admin_store._settings.clear()
    for key in (
        "CERBERUS_AUTO_SCALE",
        "CERBERUS_AUTO_TRAIN",
        "CERBERUS_LEARNING_TICK",
    ):
        monkeypatch.delenv(key, raising=False)
    yield
    admin_store._settings.clear()


def test_effective_defaults_false():
    from orchestrator.ml.flags import (
        effective_auto_scale,
        effective_auto_train,
        effective_learning_tick,
    )

    assert effective_auto_scale() is False
    assert effective_auto_train() is False
    assert effective_learning_tick() is False


def test_env_enables_when_no_override(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_SCALE", "true")
    from orchestrator.ml.flags import effective_auto_scale

    assert effective_auto_scale() is True


def test_admin_override_beats_env(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_SCALE", "true")
    from security import admin_store
    from orchestrator.ml.flags import effective_auto_scale

    admin_store.set_ops_flag("auto_scale", False)
    assert effective_auto_scale() is False
    admin_store.set_ops_flag("auto_scale", None)
    assert effective_auto_scale() is True


def test_set_ops_flag_rejects_unknown():
    from security import admin_store

    with pytest.raises(ValueError, match="unknown"):
        admin_store.set_ops_flag("nope", True)


def test_get_settings_includes_ops_keys():
    from security import admin_store

    admin_store.set_ops_flag("learning_tick", True)
    s = admin_store.get_settings()
    assert s["learning_tick"] is True
    assert "auto_scale" in s
    assert "auto_train" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/emadmousa/cerberus-x && PYTHONPATH=src pytest tests/test_ops_flags.py -v`  
Expected: FAIL (module / functions missing)

- [ ] **Step 3: Implement admin_store ops + flags module**

Add to `src/security/admin_store.py`:

```python
OPS_FLAGS = frozenset({"auto_scale", "auto_train", "learning_tick"})


def get_settings() -> dict[str, Any]:
    _load_settings()
    return {
        "rbac_enforce": _settings.get("rbac_enforce"),
        "edition": _settings.get("edition"),
        "auth_methods": _settings.get("auth_methods") or {},
        "auto_scale": _settings.get("auto_scale"),
        "auto_train": _settings.get("auto_train"),
        "learning_tick": _settings.get("learning_tick"),
    }


def _ops_override(name: str) -> Optional[bool]:
    if name not in OPS_FLAGS:
        raise ValueError(f"unknown ops flag: {name}")
    _load_settings()
    val = _settings.get(name)
    return bool(val) if val is not None else None


def auto_scale_override() -> Optional[bool]:
    return _ops_override("auto_scale")


def auto_train_override() -> Optional[bool]:
    return _ops_override("auto_train")


def learning_tick_override() -> Optional[bool]:
    return _ops_override("learning_tick")


def set_ops_flag(name: str, value: Optional[bool]) -> dict[str, Any]:
    if name not in OPS_FLAGS:
        raise ValueError(f"unknown ops flag: {name}")
    _load_settings()
    _settings[name] = None if value is None else bool(value)
    _save_settings()
    return get_settings()
```

Create `src/orchestrator/ml/__init__.py` (empty or docstring).

Create `src/orchestrator/ml/flags.py`:

```python
"""Effective ops flags: admin override → env → False."""

from __future__ import annotations

import os
from typing import Optional


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").lower() in {"1", "true", "yes", "on"}


def _resolve(override: Optional[bool], env_name: str) -> bool:
    if override is not None:
        return bool(override)
    return _env_truthy(env_name)


def effective_auto_scale() -> bool:
    from security.admin_store import auto_scale_override

    return _resolve(auto_scale_override(), "CERBERUS_AUTO_SCALE")


def effective_auto_train() -> bool:
    from security.admin_store import auto_train_override

    return _resolve(auto_train_override(), "CERBERUS_AUTO_TRAIN")


def effective_learning_tick() -> bool:
    from security.admin_store import learning_tick_override

    return _resolve(learning_tick_override(), "CERBERUS_LEARNING_TICK")
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `PYTHONPATH=src pytest tests/test_ops_flags.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/ml/__init__.py src/orchestrator/ml/flags.py \
  src/security/admin_store.py tests/test_ops_flags.py
git commit -m "$(cat <<'EOF'
feat(ops): add admin-overridable auto-scale train and learning flags

EOF
)"
```

---

### Task 2: Admin API — `PUT /api/admin/settings/ops` + GET effective

**Files:**
- Modify: `src/orchestrator/api/admin.py`
- Modify: `tests/test_admin_console.py` (or add cases to `tests/test_ops_flags.py`)
- Test: extend `tests/test_ops_flags.py` with HTTP cases

**Interfaces:**
- Consumes: `admin_store.set_ops_flag`, `effective_*`
- Produces: `PUT /api/admin/settings/ops` body `{auto_scale?, auto_train?, learning_tick?}` each `true|false|null`; GET settings includes `effective.auto_scale|auto_train|learning_tick` and `secret_key_insecure`

- [ ] **Step 1: Write the failing HTTP test**

```python
def test_admin_ops_put_and_get_effective(monkeypatch):
    monkeypatch.setenv("CERBERUS_AUTO_SCALE", "false")
    from orchestrator import dashboard

    c = dashboard.app.test_client()
    r = c.put("/api/admin/settings/ops", json={"auto_scale": True})
    assert r.status_code == 200
    assert r.get_json()["settings"]["auto_scale"] is True

    g = c.get("/api/admin/settings")
    body = g.get_json()
    assert body["effective"]["auto_scale"] is True
    assert "auto_train" in body["effective"]
    assert "learning_tick" in body["effective"]
    assert "secret_key_insecure" in body


def test_admin_ops_put_rejects_unknown():
    from orchestrator import dashboard

    c = dashboard.app.test_client()
    r = c.put("/api/admin/settings/ops", json={"nope": True})
    assert r.status_code == 400
```

- [ ] **Step 2: Run — expect FAIL** (404 or missing keys)

- [ ] **Step 3: Implement endpoint**

In `get_settings()` effective block, add:

```python
from orchestrator.ml.flags import (
    effective_auto_scale,
    effective_auto_train,
    effective_learning_tick,
)

# inside jsonify:
"effective": {
    "rbac_enforce": rbac_enforce_enabled(),
    "edition": edition(),
    "auto_scale": effective_auto_scale(),
    "auto_train": effective_auto_train(),
    "learning_tick": effective_learning_tick(),
},
"secret_key_insecure": (
    os.environ.get("SECRET_KEY", "cerberus-x-secret") == "cerberus-x-secret"
),
```

Add route:

```python
@admin_bp.put("/api/admin/settings/ops")
@require_role(Role.ADMIN)
def set_ops():
    body = _body()
    allowed = {"auto_scale", "auto_train", "learning_tick"}
    unknown = set(body.keys()) - allowed
    if unknown:
        return jsonify({"error": f"unknown keys: {sorted(unknown)}"}), 400
    if not any(k in body for k in allowed):
        return jsonify({"error": "provide at least one ops flag"}), 400
    updated = {}
    try:
        for key in allowed:
            if key not in body:
                continue
            updated[key] = body[key]
            admin_store.set_ops_flag(key, body[key])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    audit_log("ADMIN_OPS_SET", updated, severity="high")
    return jsonify({"settings": admin_store.get_settings()})
```

Import `os` at top of admin.py if missing.

- [ ] **Step 4: Run — expect PASS**

Run: `PYTHONPATH=src pytest tests/test_ops_flags.py tests/test_admin_console.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/api/admin.py tests/test_ops_flags.py
git commit -m "$(cat <<'EOF'
feat(admin): expose ops flag settings api

EOF
)"
```

---

### Task 3: Celery beat — gate scale tick + register learning/daily stubs

**Files:**
- Modify: `src/orchestrator/celery_app.py`
- Test: `tests/test_celery_ops_gates.py`

**Interfaces:**
- Consumes: `effective_auto_scale`, `effective_auto_train`, `effective_learning_tick`
- Produces: tasks `workers.scale_workers_tick`, `orchestrator.ml.learning_tick`, `orchestrator.ml.daily_pipeline` that return `{"skipped": true}` when Off

- [ ] **Step 1: Write failing gate tests**

```python
# tests/test_celery_ops_gates.py
def test_scale_tick_skips_when_off(monkeypatch):
    monkeypatch.delenv("CERBERUS_AUTO_SCALE", raising=False)
    from security import admin_store

    admin_store._settings.clear()
    admin_store.set_ops_flag("auto_scale", False)

    from orchestrator.celery_app import app

    # Import the registered task by name after configure
    from workers.scaling import DynamicScaler

    called = {"n": 0}

    def boom(self):
        called["n"] += 1
        return {}

    monkeypatch.setattr(DynamicScaler, "scale_workers", boom)

    # Call the gate wrapper directly once implemented:
    from orchestrator import celery_app as ca

    # Prefer testing a pure helper if extracted:
    from orchestrator.ml.flags import effective_auto_scale

    assert effective_auto_scale() is False
```

Prefer extracting small run helpers in celery_app or ml modules for testability:

```python
# In celery_app or ml/tasks helpers
def run_scale_workers_tick():
    from orchestrator.ml.flags import effective_auto_scale
    if not effective_auto_scale():
        return {"skipped": True, "reason": "auto_scale_off"}
    from workers.scaling import DynamicScaler
    return DynamicScaler().scale_workers()
```

Update the test to call `run_scale_workers_tick` and assert `skipped`.

Also:

```python
def test_learning_tick_skips_when_off():
    from orchestrator.ml.harvest import learning_tick
    # Task 4 implements body; for Task 3 stub:
    ...
```

**Task 3 scope:** rewrite `celery_app.py` to always register three periodic tasks whose bodies call gated helpers. Stub `learning_tick` / `run_daily_pipeline` as:

```python
def learning_tick():
    from orchestrator.ml.flags import effective_learning_tick
    if not effective_learning_tick():
        return {"skipped": True, "reason": "learning_tick_off"}
    from orchestrator.ml.harvest import run_learning_tick
    return run_learning_tick()
```

If harvest not yet present, Task 3 may define temporary stubs in `celery_app.py` that only skip-gate, and Task 4 replaces with real harvest. Prefer creating `harvest.py` / `auto_train.py` with skip-only stubs in Task 3 so imports resolve.

Minimal stubs for Task 3:

```python
# harvest.py
def run_learning_tick():
    return {"harvested": 0, "refreshed": False}

# auto_train.py
def run_daily_pipeline():
    return {"ok": True, "dry_run": True}
```

- [ ] **Step 2: Run — FAIL until celery_app updated**

- [ ] **Step 3: Rewrite `celery_app.py`**

```python
from celery import Celery
from celery.schedules import crontab
import os

app = Celery("orchestrator")
app.config_from_object("orchestrator.celeryconfig")
app.autodiscover_tasks(["orchestrator", "workers"])


def run_scale_workers_tick():
    from orchestrator.ml.flags import effective_auto_scale

    if not effective_auto_scale():
        return {"skipped": True, "reason": "auto_scale_off"}
    from workers.scaling import DynamicScaler

    return DynamicScaler().scale_workers()


@app.on_after_configure.connect
def _register_ops_periodic_tasks(sender, **kwargs):
    @app.task(name="workers.scale_workers_tick")
    def scale_workers_tick():
        return run_scale_workers_tick()

    @app.task(name="orchestrator.ml.learning_tick")
    def learning_tick_task():
        from orchestrator.ml.flags import effective_learning_tick
        from orchestrator.ml.harvest import run_learning_tick

        if not effective_learning_tick():
            return {"skipped": True, "reason": "learning_tick_off"}
        return run_learning_tick()

    @app.task(name="orchestrator.ml.daily_pipeline")
    def daily_pipeline_task():
        from orchestrator.ml.flags import effective_auto_train
        from orchestrator.ml.auto_train import run_daily_pipeline

        if not effective_auto_train():
            return {"skipped": True, "reason": "auto_train_off"}
        return run_daily_pipeline()

    sender.add_periodic_task(30.0, scale_workers_tick.s(), name="scale-workers")
    sender.add_periodic_task(60.0, learning_tick_task.s(), name="learning-tick")
    hour = int(os.environ.get("CERBERUS_AUTO_TRAIN_HOUR") or "3")
    sender.add_periodic_task(
        crontab(minute=0, hour=max(0, min(hour, 23))),
        daily_pipeline_task.s(),
        name="daily-ml-pipeline",
    )
```

Create stub modules if needed so imports succeed.

- [ ] **Step 4: Tests PASS**

```bash
PYTHONPATH=src pytest tests/test_celery_ops_gates.py tests/test_ops_flags.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/celery_app.py src/orchestrator/ml/harvest.py \
  src/orchestrator/ml/auto_train.py tests/test_celery_ops_gates.py
git commit -m "$(cat <<'EOF'
feat(celery): register gated scale learning and daily beat tasks

EOF
)"
```

---

### Task 4: Learning tick harvest implementation

**Files:**
- Modify: `src/orchestrator/ml/harvest.py`
- Test: `tests/test_ml_harvest.py`

**Interfaces:**
- Consumes: `playbook_jobs`, `normalize_record`, `scaffolds.health_all`, Redis `sadd`/`smembers`
- Produces: `run_learning_tick() -> dict` with keys `harvested`, `skipped_dup`, `health`, `path`

- [ ] **Step 1: Failing test**

```python
# tests/test_ml_harvest.py
import json
from pathlib import Path


def test_harvest_completed_mission_once(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path))
    from orchestrator.job_store import playbook_jobs
    from orchestrator.ml.harvest import run_learning_tick, HARVESTED_KEY
    from utils.redis_utils import get_redis

    r = get_redis()
    try:
        r.delete(HARVESTED_KEY)
    except Exception:
        pass

    job_id = "job-harvest-1"
    playbook_jobs[job_id] = {
        "task_id": job_id,
        "state": "SUCCESS",
        "target": "https://lab.example",
        "ai_mode": True,
        "posture": "balanced",
        "nl_goal": "authorized recon",
        "results": {
            "ai_recon": [{"tool": "nmap", "ports": [{"port": 443}]}],
        },
    }

    out1 = run_learning_tick()
    assert out1["harvested"] >= 1
    path = Path(out1["path"])
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert any(job_id in line or "lab.example" in line for line in lines)

    out2 = run_learning_tick()
    assert out2["harvested"] == 0
    assert out2.get("skipped_dup", 0) >= 1
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `run_learning_tick`**

```python
# src/orchestrator/ml/harvest.py
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
HARVESTED_KEY = "cerberus:ml:harvested"
TERMINAL = frozenset({"SUCCESS", "FAILURE", "STOPPED", "REVOKED"})


def _output_dir() -> Path:
    return Path(
        os.environ.get("CERBERUS_OUTPUT_DIR")
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
    from orchestrator.dataset.pipeline import normalize_record

    posture = job.get("posture") or (job.get("ai") or {}).get("posture") or "balanced"
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
        # Force list via summaries + local keys
        ids = set(getattr(playbook_jobs, "_local", {}).keys())
        for job_id in list(ids):
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
```

- [ ] **Step 4: PASS**

`PYTHONPATH=src pytest tests/test_ml_harvest.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/ml/harvest.py tests/test_ml_harvest.py
git commit -m "$(cat <<'EOF'
feat(ml): harvest completed missions on learning tick

EOF
)"
```

---

### Task 5: Daily ML pipeline (merge + eval dry-run)

**Files:**
- Modify: `src/orchestrator/ml/auto_train.py`
- Test: `tests/test_ml_auto_train.py`

**Interfaces:**
- Consumes: seed JSONL paths, contribution files, eval scripts (import or subprocess)
- Produces: `run_daily_pipeline() -> dict` writing `output/ml/daily_report.json`

- [ ] **Step 1: Failing test**

```python
def test_daily_pipeline_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("CERBERUS_OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("CERBERUS_TRAIN_GPU", raising=False)
    from orchestrator.ml.auto_train import run_daily_pipeline

    result = run_daily_pipeline()
    assert result.get("ok") is True
    assert result.get("gpu_train") is False
    report = tmp_path / "ml" / "daily_report.json"
    assert report.is_file()
    data = json.loads(report.read_text())
    assert "schema_eval" in data or "steps" in data
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

```python
# src/orchestrator/ml/auto_train.py
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


def _run_script(rel: str) -> dict[str, Any]:
    script = _repo_root() / rel
    if not script.is_file():
        return {"ok": False, "error": f"missing {rel}"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
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
    # Optional merge of posture seeds if script exists
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
        steps["qlora"]["result"] = _run_script("training/scripts/qlora_train.py")
    else:
        # Prefer --dry-run if script supports it; otherwise skip
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
            except Exception as exc:
                steps["qlora"]["error"] = str(exc)

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
```

If `qlora_train.py` has no `--dry-run`, catch and set `steps["qlora"]["mode"]="skipped_no_dry_run"`.

- [ ] **Step 4: PASS**

`PYTHONPATH=src pytest tests/test_ml_auto_train.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/ml/auto_train.py tests/test_ml_auto_train.py
git commit -m "$(cat <<'EOF'
feat(ml): add daily merge and eval auto-train pipeline

EOF
)"
```

---

### Task 6: Redis Flask-Session

**Files:**
- Create: `src/orchestrator/session_config.py`
- Modify: `src/orchestrator/dashboard.py` (after SECRET_KEY)
- Modify: `requirements.txt`
- Modify: `.env.example`
- Test: `tests/test_session_config.py`

**Interfaces:**
- Consumes: `get_redis()`, Flask app
- Produces: `configure_sessions(app) -> dict` with `{"backend": "redis"|"cookie", "secure": bool}`

- [ ] **Step 1: Failing test**

```python
def test_configure_sessions_cookie_fallback(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-default")
    from flask import Flask
    from orchestrator.session_config import configure_sessions

    app = Flask("t")
    app.config["SECRET_KEY"] = "test-secret-key-not-default"
    # Force cookie path by making redis look like MemoryRedis
    info = configure_sessions(app, force_cookie=True)
    assert info["backend"] == "cookie"


def test_default_secret_flag():
    from orchestrator.session_config import secret_key_is_insecure

    assert secret_key_is_insecure("cerberus-x-secret") is True
    assert secret_key_is_insecure("real-secret") is False
```

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Implement**

```python
# src/orchestrator/session_config.py
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any

logger = logging.getLogger(__name__)
DEFAULT_SECRET = "cerberus-x-secret"


def secret_key_is_insecure(secret: str | None = None) -> bool:
    value = secret if secret is not None else os.environ.get("SECRET_KEY", DEFAULT_SECRET)
    return (value or DEFAULT_SECRET) == DEFAULT_SECRET


def configure_sessions(app, *, force_cookie: bool = False) -> dict[str, Any]:
    secure = (os.environ.get("CERBERUS_SESSION_SECURE") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = secure
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

    if secret_key_is_insecure(app.config.get("SECRET_KEY")):
        logger.warning(
            "SECRET_KEY is the insecure default; set a strong SECRET_KEY in production"
        )

    if force_cookie:
        return {"backend": "cookie", "secure": secure}

    try:
        from flask_session import Session
        from utils.redis_utils import get_redis
        import redis as redis_lib

        client = get_redis()
        if not isinstance(client, redis_lib.Redis):
            logger.warning("Redis sessions unavailable (memory fallback); using cookies")
            return {"backend": "cookie", "secure": secure}

        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = client
        app.config["SESSION_KEY_PREFIX"] = "cerberus:sess:"
        app.config["SESSION_USE_SIGNER"] = True
        app.config["SESSION_PERMANENT"] = False
        Session(app)
        return {"backend": "redis", "secure": secure}
    except Exception as exc:
        logger.warning("Flask-Session Redis setup failed (%s); using cookies", exc)
        return {"backend": "cookie", "secure": secure}
```

In `dashboard.py` after SECRET_KEY / config:

```python
from orchestrator.session_config import configure_sessions

configure_sessions(app)
```

`requirements.txt` add: `Flask-Session==0.8.0` (pin a version that supports Flask 3; adjust if install fails).

`.env.example` add near SECRET_KEY / AUTO_SCALE:

```
# Server-side sessions (Flask-Session → Redis). Secure cookie flag for HTTPS.
CERBERUS_SESSION_SECURE=false
# Daily ML + learning tick (also toggleable in Admin → Ops)
CERBERUS_AUTO_TRAIN=false
CERBERUS_AUTO_TRAIN_HOUR=3
CERBERUS_LEARNING_TICK=false
CERBERUS_TRAIN_GPU=false
```

- [ ] **Step 4: PASS** + `pip install Flask-Session==0.8.0` in the env used by tests

- [ ] **Step 5: Commit**

```bash
git add src/orchestrator/session_config.py src/orchestrator/dashboard.py \
  requirements.txt .env.example tests/test_session_config.py
git commit -m "$(cat <<'EOF'
feat(auth): store flask sessions in redis when available

EOF
)"
```

---

### Task 7: FirebreakPanel — Load all / Submit all

**Files:**
- Modify: `frontend/src/components/FirebreakPanel.tsx`
- Create: `frontend/src/__tests__/FirebreakPanel.bulk.test.tsx`
- Optional: `frontend/src/api/client.ts` (no API change required)

**Interfaces:**
- Consumes: `contributeDataset`, existing `examples` state
- Produces: UI buttons `Load all (posture)`, `Submit all (CC-BY)`; state `bulkRows: Array<{id,label,prompt,response,checked}>`

- [ ] **Step 1: Failing Vitest**

```tsx
// frontend/src/__tests__/FirebreakPanel.bulk.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { FirebreakPanel } from "../components/FirebreakPanel";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    getFirebreakStatus: vi.fn(async () => ({ model: "m", base_model: "b" })),
    getScaffolds: vi.fn(async () => ({ health: [] })),
    getMarketplace: vi.fn(async () => null),
    getEditionStatus: vi.fn(async () => ({})),
    getDatasetExamples: vi.fn(async () => ({
      examples: [
        { id: "a1", label: "A1", prompt: "p1", response: "r1" },
        { id: "a2", label: "A2", prompt: "p2", response: "r2" },
      ],
      guidance: "g",
    })),
    contributeDataset: vi.fn(async () => ({ persisted: true, record: { id: "x" } })),
  };
});

import { contributeDataset } from "../api/client";

test("load all stages examples and submit all contributes each", async () => {
  render(<FirebreakPanel />);
  const loadAll = await screen.findByRole("button", { name: /load all/i });
  fireEvent.click(loadAll);
  expect(await screen.findByText(/2 selected|2 ready/i)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /submit all/i }));
  await waitFor(() => {
    expect(contributeDataset).toHaveBeenCalledTimes(2);
  });
});
```

Adjust matchers to the exact copy you implement (`Load all (posture)`, `Submit all (CC-BY)`, status like `Bulk: 2/2 saved`).

- [ ] **Step 2: Run — FAIL**

`cd frontend && npm test -- --run src/__tests__/FirebreakPanel.bulk.test.tsx`

- [ ] **Step 3: Implement UI in FirebreakPanel**

State:

```tsx
type BulkRow = ContribExample & { checked: boolean };
const [bulk, setBulk] = useState<BulkRow[]>([]);
const [bulkMsg, setBulkMsg] = useState<string | null>(null);
```

Handlers:

```tsx
function loadAllExamples() {
  setBulk(examples.map((e) => ({ ...e, checked: true })));
  setBulkMsg(`Staged ${examples.length} examples`);
}

async function submitAll() {
  const rows = bulk.filter((b) => b.checked && b.prompt.trim() && b.response.trim());
  let saved = 0;
  const errors: string[] = [];
  for (const row of rows) {
    try {
      await contributeDataset({
        prompt: row.prompt,
        response: row.response,
        posture: examplePosture || row.posture || "balanced",
        license: "CC-BY-4.0",
        contributor: "mission-control",
      });
      saved += 1;
      setBulkMsg(`Saved ${saved}/${rows.length}`);
    } catch (err: unknown) {
      errors.push(`${row.id}: ${err instanceof Error ? err.message : String(err)}`);
    }
  }
  setBulkMsg(
    errors.length
      ? `Saved ${saved}/${rows.length}; errors: ${errors.join("; ")}`
      : `Saved ${saved}/${rows.length}`,
  );
}
```

UI under the example select: buttons + checklist of `bulk` with checkboxes.

Extend `ContribExample` with optional `posture?: string`.

- [ ] **Step 4: PASS** + existing MissionControl tests

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/FirebreakPanel.tsx \
  frontend/src/__tests__/FirebreakPanel.bulk.test.tsx
git commit -m "$(cat <<'EOF'
feat(ui): add load-all and submit-all dataset examples

EOF
)"
```

---

### Task 8: Admin Ops tab

**Files:**
- Modify: `frontend/src/views/Admin.tsx`
- Modify: `frontend/src/api/client.ts` (`AdminSettings`, `setOpsSettings`)
- Create: `frontend/src/__tests__/Admin.ops.test.tsx`

**Interfaces:**
- Consumes: `GET /api/admin/settings`, `PUT /api/admin/settings/ops`
- Produces: Ops tab with three On/Off/Defer radio groups

- [ ] **Step 1: Extend client types + failing UI test**

```ts
// client.ts — extend AdminSettings
settings: {
  rbac_enforce: boolean | null;
  edition: string | null;
  auth_methods: Record<string, boolean>;
  auto_scale: boolean | null;
  auto_train: boolean | null;
  learning_tick: boolean | null;
};
effective: {
  rbac_enforce: boolean;
  edition: string;
  auto_scale: boolean;
  auto_train: boolean;
  learning_tick: boolean;
};
secret_key_insecure?: boolean;

export async function setOpsSettings(body: {
  auto_scale?: boolean | null;
  auto_train?: boolean | null;
  learning_tick?: boolean | null;
}): Promise<AdminSettings["settings"]> {
  const d = await apiJson<{ settings: AdminSettings["settings"] }>(
    "/api/admin/settings/ops",
    { method: "PUT", body: JSON.stringify(body) },
  );
  return d.settings;
}
```

Test: render Admin with mocked settings; click Ops tab; click Auto-Scale ON; expect `setOpsSettings` called with `{ auto_scale: true }`.

- [ ] **Step 2: FAIL**

- [ ] **Step 3: Add Ops tab** (mirror `RbacTab` radio pattern)

```tsx
type TabId = ... | "ops";
// TABS push { id: "ops", label: "Ops" }

function OpsTab({ flash }: { flash: FlashFn }) {
  // load getAdminSettings
  // for each flag: On / Off / Defer
  // show Effective: ON/OFF
  // warn if settings.secret_key_insecure
}
```

Wire `setOpsSettings({ [flag]: value })`.

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/Admin.tsx frontend/src/api/client.ts \
  frontend/src/__tests__/Admin.ops.test.tsx
git commit -m "$(cat <<'EOF'
feat(admin): add ops tab for auto-scale train and learning tick

EOF
)"
```

---

### Task 9: Docs polish + regression sweep

**Files:**
- Modify: `docs/user_manual.md` (short Ops + bulk examples + schedulers section)
- Modify: `docs/api_reference.md` (ops endpoint row)
- Modify: `.env.example` if any keys missing from Task 6

- [ ] **Step 1: Document** Admin → Ops toggles; note one-shot `/api/scale/auto` always available; Learning Tick / Auto-Train behavior; Load all / Submit all on Firebreak panel.

- [ ] **Step 2: Run full relevant suites**

```bash
cd /Users/emadmousa/cerberus-x
PYTHONPATH=src pytest tests/test_ops_flags.py tests/test_celery_ops_gates.py \
  tests/test_ml_harvest.py tests/test_ml_auto_train.py tests/test_session_config.py \
  tests/test_admin_console.py -v
cd frontend && npm test -- --run
```

Expected: all PASS (fix any regressions introduced).

- [ ] **Step 3: Commit**

```bash
git add docs/user_manual.md docs/api_reference.md .env.example
git commit -m "$(cat <<'EOF'
docs: document sessions ops toggles and scheduled learning

EOF
)"
```

---

## Spec coverage checklist

| Spec section | Task |
|--------------|------|
| Redis sessions | 6 |
| Load all / Submit all | 7 |
| Daily ML | 5 (+ beat in 3) |
| Learning tick | 4 (+ beat in 3) |
| Admin Ops + Auto-Scale | 1, 2, 8 (+ scale gate in 3) |
| Env flags / .env.example | 6, 9 |
| secret_key_insecure | 2, 6, 8 |
| Tests | each task |
| One-shot scale ungated | 3 (do not wrap `/api/scale/auto`) |

## Self-review notes

- No TBD placeholders; stubs in Task 3 are concrete and replaced in 4–5.
- Flag names consistent: `auto_scale`, `auto_train`, `learning_tick`.
- Effective helpers always imported from `orchestrator.ml.flags`.
