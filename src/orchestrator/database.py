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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS state (
                target TEXT PRIMARY KEY,
                state_json TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

def save_phase_result(target, phase_name, phase_outputs):
    with get_db() as conn:
        if isinstance(phase_outputs, list):
            for item in phase_outputs:
                if isinstance(item, dict) and 'tool' in item:
                    conn.execute(
                        'INSERT INTO results (target, phase, tool, result_json) VALUES (?, ?, ?, ?)',
                        (target, phase_name, item.get('tool'), json.dumps(item))
                    )
        elif isinstance(phase_outputs, dict):
            for tool_name, result_data in phase_outputs.items():
                conn.execute(
                    'INSERT INTO results (target, phase, tool, result_json) VALUES (?, ?, ?, ?)',
                    (target, phase_name, tool_name, json.dumps(result_data))
                )
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

def save_state(target: str, state: dict):
    with get_db() as conn:
        conn.execute(
            'REPLACE INTO state (target, state_json) VALUES (?, ?)',
            (target, json.dumps(state))
        )
        conn.commit()

def load_state(target: str) -> dict:
    with get_db() as conn:
        cursor = conn.execute('SELECT state_json FROM state WHERE target = ?', (target,))
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return {}