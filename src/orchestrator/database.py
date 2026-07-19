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
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
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


def _maybe_index_es(target, phase_name, tool_name, payload):
    try:
        from .elasticsearch_client import ElasticsearchClient

        client = ElasticsearchClient()
        if client.available:
            client.index_result(target, phase_name, tool_name, payload)
    except Exception as exc:
        logger.debug("Elasticsearch index skipped: %s", exc)


def save_phase_result(target, phase_name, phase_outputs):
    rows = _normalize_phase_outputs(phase_outputs)
    with get_db() as conn:
        for tool_name, payload in rows:
            conn.execute(
                "INSERT INTO results (target, phase, tool, result_json) VALUES (?, ?, ?, ?)",
                (target, phase_name, tool_name, json.dumps(payload)),
            )
            _maybe_index_es(target, phase_name, tool_name, payload)
        conn.commit()
    paths = export_target_reports(target, get_results(target, limit=10000))
    print(
        f"[+] Wrote reports for {target}: "
        f"{paths['json']} | {paths['html']}"
    )


def get_results(target=None, limit=100):
    with get_db() as conn:
        if target:
            cursor = conn.execute(
                "SELECT target, phase, tool, result_json, timestamp FROM results "
                "WHERE target = ? ORDER BY timestamp DESC LIMIT ?",
                (target, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT target, phase, tool, result_json, timestamp FROM results "
                "ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = cursor.fetchall()
        return [
            {
                "target": row[0],
                "phase": row[1],
                "tool": row[2],
                "result": json.loads(row[3]),
                "timestamp": row[4],
            }
            for row in rows
        ]


def save_state(target: str, state: dict):
    with get_db() as conn:
        conn.execute(
            "REPLACE INTO state (target, state_json) VALUES (?, ?)",
            (target, json.dumps(state)),
        )
        conn.commit()


def load_state(target: str) -> dict:
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT state_json FROM state WHERE target = ?",
            (target,),
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return {}
