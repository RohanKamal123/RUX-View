import sqlite3
import os
from datetime import datetime

DB_PATH = "visitors.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id        INTEGER NOT NULL DEFAULT 1,
            camera_name      TEXT    NOT NULL DEFAULT 'Camera',
            timestamp        TEXT    NOT NULL,
            snapshot_path    TEXT,
            peak_count       INTEGER NOT NULL DEFAULT 1,
            status           TEXT    NOT NULL DEFAULT 'completed',
            start_time       TEXT,
            end_time         TEXT,
            duration_seconds INTEGER,
            starred          INTEGER NOT NULL DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS names (
            session_id  INTEGER PRIMARY KEY,
            name        TEXT NOT NULL
        )
    """)

    # Migrate existing DB safely
    migrations = [
        'ALTER TABLE visitors ADD COLUMN camera_id INTEGER NOT NULL DEFAULT 1',
        'ALTER TABLE visitors ADD COLUMN camera_name TEXT NOT NULL DEFAULT "Camera"',
        'ALTER TABLE visitors ADD COLUMN peak_count INTEGER NOT NULL DEFAULT 1',
        'ALTER TABLE visitors ADD COLUMN status TEXT NOT NULL DEFAULT "completed"',
        'ALTER TABLE visitors ADD COLUMN start_time TEXT',
        'ALTER TABLE visitors ADD COLUMN end_time TEXT',
        'ALTER TABLE visitors ADD COLUMN duration_seconds INTEGER',
        'ALTER TABLE visitors ADD COLUMN starred INTEGER NOT NULL DEFAULT 0',
    ]
    for sql in migrations:
        try:
            c.execute(sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


# ── Write ─────────────────────────────────────────────────────────────────────

def log_visitor(camera_id: int, camera_name: str,
                snapshot_path: str | None = None, peak_count: int = 1) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO visitors
            (camera_id, camera_name, timestamp, snapshot_path,
             peak_count, status, start_time, end_time, duration_seconds, starred)
        VALUES (?, ?, ?, ?, ?, 'completed', ?, ?, 0, 0)
    """, (camera_id, camera_name, now, snapshot_path, peak_count, now, now))
    conn.commit()
    conn.close()
    return now


def save_name(session_id: int, name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if name:
        c.execute("""
            INSERT INTO names (session_id, name) VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET name=excluded.name
        """, (session_id, name))
    else:
        c.execute("DELETE FROM names WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


def toggle_star(session_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT starred FROM visitors WHERE id = ?", (session_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    new_val = 0 if row[0] else 1
    c.execute("UPDATE visitors SET starred = ? WHERE id = ?", (new_val, session_id))
    conn.commit()
    conn.close()
    return bool(new_val)


# ── Read ──────────────────────────────────────────────────────────────────────

def get_sessions(filter: str = "all", limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    sql = """
        SELECT id, camera_id, camera_name, timestamp, snapshot_path,
               peak_count, status, start_time, end_time, duration_seconds, starred
        FROM visitors
    """
    if filter == "starred":
        sql += " WHERE starred = 1"

    sql += " ORDER BY id DESC LIMIT ?"
    c.execute(sql, (limit,))
    rows = c.fetchall()
    conn.close()

    return [
        {
            "id":               r[0],
            "camera_id":        r[1],
            "camera_name":      r[2],
            "timestamp":        r[3],
            "snapshot_path":    r[4],
            "peak_count":       r[5] or 1,
            "status":           r[6] or "completed",
            "start_time":       r[7] or r[3],
            "end_time":         r[8] or r[3],
            "duration_seconds": r[9],
            "starred":          bool(r[10]),
        }
        for r in rows
    ]


def get_names() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT session_id, name FROM names")
    rows = c.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def get_recent_visitors(limit: int = 20):
    """Kept for backward compatibility."""
    return get_sessions(limit=limit)


def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM visitors")
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM visitors WHERE status = 'active'")
    active = c.fetchone()[0]

    c.execute("""
        SELECT AVG(duration_seconds) FROM visitors
        WHERE duration_seconds IS NOT NULL AND duration_seconds > 0
    """)
    avg = c.fetchone()[0]
    avg_duration = round(avg) if avg else 0

    c.execute("SELECT MAX(peak_count) FROM visitors")
    row = c.fetchone()
    max_people = row[0] if row and row[0] else 0

    c.execute("""
        SELECT COUNT(*) FROM visitors
        WHERE timestamp >= datetime('now', '-1 day')
    """)
    today = c.fetchone()[0]

    c.execute("""
        SELECT camera_name, COUNT(*) as cnt
        FROM visitors
        GROUP BY camera_name
        ORDER BY cnt DESC
    """)
    per_camera = [{"camera": r[0], "count": r[1]} for r in c.fetchall()]

    conn.close()
    return {
        "total":        total,
        "active":       active,
        "avg_duration": avg_duration,
        "max_people":   max_people,
        "today":        today,
        "per_camera":   per_camera,
    }
