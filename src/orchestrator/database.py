import json
import logging
import os
import sqlite3

from .reporting import export_target_reports

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get(
    "CERBERUS_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "results.db"),
)


def get_db():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                phase TEXT NOT NULL,
                tool TEXT,
                result_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                job_id TEXT
            )
            """
        )
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(results)").fetchall()
        }
        if "job_id" not in cols:
            conn.execute("ALTER TABLE results ADD COLUMN job_id TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS state (
                target TEXT PRIMARY KEY,
                state_json TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def _normalize_phase_outputs(phase_outputs):
    """Normalize list/dict/single-tool outputs into (tool, payload) rows."""
    rows = []
    if isinstance(phase_outputs, list):
        for item in phase_outputs:
            if isinstance(item, dict) and "tool" in item:
                rows.append((item.get("tool"), item))
        return rows

    if isinstance(phase_outputs, dict):
        if "tool" in phase_outputs:
            return [(phase_outputs.get("tool"), phase_outputs)]
        for tool_name, result_data in phase_outputs.items():
            rows.append((tool_name, result_data))
    return rows


def _maybe_index_es(target, phase_name, tool_name, payload, job_id=None):
    try:
        from .elasticsearch_client import ElasticsearchClient

        client = ElasticsearchClient()
        if client.available:
            client.index_result(target, phase_name, tool_name, payload, job_id=job_id)
    except Exception as exc:
        logger.debug("Elasticsearch index skipped: %s", exc)


def save_phase_result(target, phase_name, phase_outputs, job_id=None):
    init_db()
    rows = _normalize_phase_outputs(phase_outputs)
    with get_db() as conn:
        for tool_name, payload in rows:
            conn.execute(
                "INSERT INTO results (target, phase, tool, result_json, job_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (target, phase_name, tool_name, json.dumps(payload), job_id),
            )
            _maybe_index_es(target, phase_name, tool_name, payload, job_id=job_id)
        conn.commit()
    paths = export_target_reports(target, get_results(target, limit=10000))
    print(
        f"[+] Wrote reports for {target}: "
        f"{paths['json']} | {paths['html']}"
    )


def get_results(target=None, limit=100, job_id=None):
    init_db()
    with get_db() as conn:
        clauses = []
        params: list = []
        if target:
            clauses.append("target = ?")
            params.append(target)
        if job_id:
            clauses.append("job_id = ?")
            params.append(job_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cursor = conn.execute(
            f"SELECT target, phase, tool, result_json, timestamp, job_id "
            f"FROM results {where} ORDER BY timestamp DESC LIMIT ?",
            params,
        )
        rows = cursor.fetchall()
        return [
            {
                "target": row[0],
                "phase": row[1],
                "tool": row[2],
                "result": json.loads(row[3]),
                "timestamp": row[4],
                "job_id": row[5],
            }
            for row in rows
        ]


def _state_key(target: str, job_id: str | None = None) -> str:
    if job_id:
        return f"{target}::{job_id}"
    return target


def save_state(target: str, state: dict, job_id: str | None = None):
    init_db()
    with get_db() as conn:
        conn.execute(
            "REPLACE INTO state (target, state_json) VALUES (?, ?)",
            (_state_key(target, job_id), json.dumps(state)),
        )
        conn.commit()


def load_state(target: str, job_id: str | None = None) -> dict:
    init_db()
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT state_json FROM state WHERE target = ?",
            (_state_key(target, job_id),),
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return {}
