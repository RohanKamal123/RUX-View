#!/usr/bin/env python3
"""
Simple macOS agent:
- Tracks frontmost app
- Counts keyboard & mouse events (counts only)
- Idle detection (2 minutes)
- Productive = frontmost in EDITING_APPS and not idle and input detected
- Aggregates per-minute and stores/sends
"""

import time, threading, sqlite3, json, os, subprocess
from datetime import datetime, timezone
from dateutil import tz
from pynput import keyboard, mouse
import requests

# CONFIG
EMPLOYEE_ID = "emp_123"     # change per-install
BACKEND_URL = "https://your-backend.example.com/ingest"  # change to your server
API_KEY = "PUT_API_KEY_HERE"
SEND_INTERVAL = 60         # seconds to send batches
AGG_INTERVAL = 60          # seconds to aggregate entries
IDLE_SECONDS = 120         # idle threshold
EDITING_APPS = {"Premiere Pro", "After Effects", "Final Cut", "DaVinci Resolve", "Photoshop"}

# local sqlite DB
DB_PATH = os.path.expanduser("~/agent_logs.db")

# in-memory counters
state = {
    "keyboard_events": 0,
    "mouse_events": 0,
    "last_input_ts": time.time(),
    "current_front_app": None,
    "current_front_app_since": time.time(),
    "pending_records": []
}

# --- helpers ---
def now_iso():
    return datetime.now(timezone.utc).isoformat()

def init_db():
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
    )""")
    conn.commit()
    conn.close()

# --- frontmost app detection (try AppKit then fallback to osascript) ---
def get_frontmost_app_name():
    try:
        # try pyobjc AppKit (faster)
        from AppKit import NSWorkspace
        ws = NSWorkspace.sharedWorkspace()
        app = ws.frontmostApplication()
        name = app.localizedName()
        return str(name)
    except Exception:
        # fallback: osascript
        try:
            cmd = ['osascript', '-e', 'tell application "System Events" to get name of first application process whose frontmost is true']
            name = subprocess.check_output(cmd, text=True).strip()
            return name
        except Exception:
            return "Unknown"

# --- input listeners ---
def on_key(_):
    state['keyboard_events'] += 1
    state['last_input_ts'] = time.time()

def on_mouse(_x, _y):
    state['mouse_events'] += 1
    state['last_input_ts'] = time.time()

def start_listeners():
    kb_listener = keyboard.Listener(on_press=on_key)
    ms_listener = mouse.Listener(on_move=on_mouse, on_click=lambda *a: on_mouse(None, None), on_scroll=lambda *a: on_mouse(None, None))
    kb_listener.start()
    ms_listener.start()
    return kb_listener, ms_listener

# --- aggregation / logic ---
def is_idle():
    return (time.time() - state['last_input_ts']) > IDLE_SECONDS

def is_editing_app(app_name):
    # basic matching: includes or equals
    if not app_name:
        return False
    for name in EDITING_APPS:
        if name.lower() in app_name.lower():
            return True
    return False

def aggregate_and_record():
    """
    Called every AGG_INTERVAL seconds to create a minute-level row.
    """
    app = state['current_front_app'] or get_frontmost_app_name()
    idle = is_idle()
    last_input = state['last_input_ts']
    # Define active time for this interval:
    # If idle => idle_seconds = AGG_INTERVAL, active_seconds = 0
    if idle:
        active_seconds = 0
        idle_seconds = AGG_INTERVAL
    else:
        # if not idle, treat full interval as active (coarse)
        active_seconds = AGG_INTERVAL
        idle_seconds = 0

    # Productive = app is editing app AND not idle AND there was input in last AGG_INTERVAL
    input_count = state['keyboard_events'] + state['mouse_events']
    productive = is_editing_app(app) and (not idle) and (input_count > 0)

    record = {
        "employee_id": EMPLOYEE_ID,
        "app_name": app,
        "active_seconds": active_seconds if productive else 0,  # only count productive as active
        "idle_seconds": idle_seconds,
        "date": datetime.now().date().isoformat(),
        "timestamp": now_iso()
    }

    # store to local sqlite immediately
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO activity (employee_id, app_name, active_seconds, idle_seconds, date, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (record['employee_id'], record['app_name'], record['active_seconds'], record['idle_seconds'], record['date'], record['timestamp']))
    conn.commit()
    conn.close()

    # queue to send
    state['pending_records'].append(record)

    # reset event counters after aggregation
    state['keyboard_events'] = 0
    state['mouse_events'] = 0

def front_app_monitor_loop(poll_seconds=1):
    while True:
        app = get_frontmost_app_name()
        if app != state['current_front_app']:
            state['current_front_app'] = app
            state['current_front_app_since'] = time.time()
        time.sleep(poll_seconds)

def aggregator_loop():
    while True:
        time.sleep(AGG_INTERVAL)
        try:
            aggregate_and_record()
        except Exception as e:
            print("Aggregation error:", e)

def sender_loop():
    while True:
        time.sleep(SEND_INTERVAL)
        if not state['pending_records']:
            continue
        batch = state['pending_records'][:]
        # attempt send
        try:
            headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
            resp = requests.post(BACKEND_URL, json={"records": batch}, headers=headers, timeout=10)
            if resp.status_code == 200:
                # clear sent items
                state['pending_records'] = []
            else:
                print("Server returned", resp.status_code, resp.text)
        except Exception as e:
            print("Send failed:", e)
            # keep pending for retry next cycle

def main():
    init_db()
    print("Starting listeners...")
    start_listeners()
    # start threads
    threading.Thread(target=front_app_monitor_loop, daemon=True).start()
    threading.Thread(target=aggregator_loop, daemon=True).start()
    threading.Thread(target=sender_loop, daemon=True).start()
    print("Agent running. Press Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting.")

if __name__ == "__main__":
    main()
