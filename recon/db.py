import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    ledger_count INTEGER NOT NULL,
    custodian_count INTEGER NOT NULL,
    matched INTEGER NOT NULL,
    explanation_mode TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    trade_id TEXT NOT NULL,
    break_type TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_breaks_run ON breaks(run_id);
"""


def init(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript(SCHEMA)


def save_run(path, result, mode):
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO runs (created_at, ledger_count, custodian_count, matched, explanation_mode) VALUES (?, ?, ?, ?, ?)",
                (created, result.ledger_count, result.custodian_count, result.matched, mode),
            )
            run_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO breaks (run_id, trade_id, break_type, payload) VALUES (?, ?, ?, ?)",
                [(run_id, b.trade_id, b.break_type, json.dumps(b.to_dict())) for b in result.breaks],
            )
    return run_id


def get_run(path, run_id):
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            return None
        rows = conn.execute(
            "SELECT break_type, payload FROM breaks WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    by_type = {}
    for row in rows:
        by_type[row["break_type"]] = by_type.get(row["break_type"], 0) + 1
    return {
        "id": run["id"],
        "created_at": run["created_at"],
        "summary": {
            "ledger_count": run["ledger_count"],
            "custodian_count": run["custodian_count"],
            "matched": run["matched"],
            "break_count": len(rows),
            "by_type": by_type,
            "explanation_mode": run["explanation_mode"],
        },
        "breaks": [json.loads(row["payload"]) for row in rows],
    }


def list_runs(path):
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT r.id, r.created_at, r.matched, r.explanation_mode, "
            "(SELECT COUNT(*) FROM breaks b WHERE b.run_id = r.id) AS break_count "
            "FROM runs r ORDER BY r.id DESC LIMIT 50"
        ).fetchall()
    return [dict(row) for row in rows]
