import sqlite3
import json
import os
from datetime import datetime

from .reporting import export_target_reports

DB_PATH = os.environ.get(
    'CERBERUS_DB_PATH',
    os.path.join(os.path.dirname(__file__), '..', '..', 'results.db'),
)

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    """Create the results table if it doesn't exist."""
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                phase TEXT NOT NULL,
                tool TEXT,
                result_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def save_phase_result(target, phase_name, phase_outputs):
    """
    Save each tool's result from a phase to the database.
    phase_outputs is a list of tool result dicts (chain or group).
    """
    with get_db() as conn:
        items = phase_outputs
        if isinstance(phase_outputs, dict):
            items = list(phase_outputs.values())
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if isinstance(item, dict) and 'tool' in item:
                conn.execute(
                    'INSERT INTO results (target, phase, tool, result_json) VALUES (?, ?, ?, ?)',
                    (target, phase_name, item.get('tool'), json.dumps(item))
                )
        conn.commit()
    export_target_reports(target, get_results(target, limit=10000))

def get_results(target=None, limit=100):
    """Retrieve results, optionally filtered by target."""
    with get_db() as conn:
        if target:
            cursor = conn.execute(
                'SELECT target, phase, tool, result_json, timestamp FROM results WHERE target = ? ORDER BY timestamp DESC LIMIT ?',
                (target, limit)
            )
        else:
            cursor = conn.execute(
                'SELECT target, phase, tool, result_json, timestamp FROM results ORDER BY timestamp DESC LIMIT ?',
                (limit,)
            )
        rows = cursor.fetchall()
        return [
            {
                'target': row[0],
                'phase': row[1],
                'tool': row[2],
                'result': json.loads(row[3]),
                'timestamp': row[4]
            }
            for row in rows
        ]