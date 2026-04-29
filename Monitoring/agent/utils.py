import os
import sqlite3
from datetime import datetime, timezone

# Path to local SQLite database
DB_PATH = os.path.expanduser("~/agent_logs.db")


# ----------------------------
# TIME HELPERS
# ----------------------------
def now_iso():
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# ----------------------------
# DATABASE HELPERS
# ----------------------------
def init_db():
    """
    Create the SQLite database (if not exists)
    with a table for activity logs.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        app_name TEXT,
        active_seconds INTEGER,
        idle_seconds INTEGER,
        date TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()


def insert_record(employee_id, app_name, active_seconds, idle_seconds, date, created_at):
    """
    Insert a new activity record into SQLite DB.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO activity (employee_id, app_name, active_seconds, idle_seconds, date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (employee_id, app_name, active_seconds, idle_seconds, date, created_at))
    conn.commit()
    conn.close()
