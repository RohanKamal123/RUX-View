# ----------------------------------------------------------------------
# Python Activity Tracker for Windows
# Requires the following libraries:
# pip install pynput pywin32 requests
# ----------------------------------------------------------------------

import time
import threading
import datetime
import win32gui
import win32process
import win32api
import os
import requests

from pynput import keyboard
from pynput import mouse

# --- Configuration ---
LOG_INTERVAL_SECONDS = 10
IDLE_THRESHOLD_SECONDS = 120

# --- Delayed Activation Thresholds ---
WAKE_KEYS = 2
WAKE_MOVES = 3
WAKE_CLICKS = 1

# List of application names (or partial titles) to monitor
TRACKED_APPS = ["Visual Studio Code", "Thonny", "Chrome", "Telegram"]

# --- Global Counters for Activity ---
key_presses = 0
mouse_clicks = 0
mouse_movements = 0
last_activity_time = time.time()

# --- Global Variables for Idle State ---
is_idle_detected = False
lock = threading.Lock()

# --- Active Window Tracker and Tracking Utilities ---

def get_process_app_name(hwnd):
    """
    Retrieves the actual application executable name (e.g., 'Chrome') 
    from the window handle (hwnd).
    """
    if not hwnd:
        return "N/A"
    
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        PROCESS_QUERY_INFORMATION = 0x0400
        process_handle = win32api.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        executable_path = win32process.GetModuleFileNameEx(process_handle, 0)
        win32api.CloseHandle(process_handle)
        process_filename = os.path.basename(executable_path)
        app_name = process_filename.rsplit('.', 1)[0]
        return app_name.capitalize()
    except Exception:
        return "Unknown_App"

def get_active_window_title(hwnd):
    """Uses pywin32 to get the title of the currently focused window using its handle."""
    try:
        title = win32gui.GetWindowText(hwnd)
        return title if title else "N/A (Desktop/Unknown)"
    except Exception as e:
        return f"Error fetching window title: {e}"

def is_current_app_tracked(active_window_title):
    """
    Checks if the active window title contains any of the TRACKED_APPS names (case-insensitive).
    """
    if not active_window_title:
        return False
    
    normalized_title = active_window_title.lower()
    return any(app.lower() in normalized_title for app in TRACKED_APPS)


# --- Listener Callbacks ---

def on_key_press(key):
    """
    Callback function executed every time a key is pressed.
    """
    global key_presses, last_activity_time, is_idle_detected
    with lock:
        key_presses += 1
        
        hwnd = win32gui.GetForegroundWindow()
        window_title = get_active_window_title(hwnd)
        is_tracked = is_current_app_tracked(window_title)
        
        if not is_tracked:
            return

        if not is_idle_detected:
            last_activity_time = time.time()

def on_mouse_click(x, y, button, pressed):
    """
    Callback function executed every time the mouse is clicked.
    """
    global mouse_clicks, last_activity_time, is_idle_detected
    if pressed:
        with lock:
            mouse_clicks += 1
            
            hwnd = win32gui.GetForegroundWindow()
            window_title = get_active_window_title(hwnd)
            is_tracked = is_current_app_tracked(window_title)
            
            if not is_idle_detected and is_tracked:
                last_activity_time = time.time()

def on_mouse_move(x, y):
    """
    Callback function executed every time the mouse is moved.
    """
    global mouse_movements, last_activity_time, is_idle_detected
    
    with lock:
        hwnd = win32gui.GetForegroundWindow()
        window_title = get_active_window_title(hwnd)
        is_tracked = is_current_app_tracked(window_title)

        if not is_idle_detected and is_tracked:
            last_activity_time = time.time()
        
        if mouse_movements % 10 == 0:
            mouse_movements += 1

    return True

# --- Logging Function ---

def log_activity():
    """
    Collects current data, determines idle state, checks for re-activation, 
    and sends it to the backend API.
    """
    global key_presses, mouse_clicks, mouse_movements, last_activity_time, is_idle_detected

    now = time.time()
    timestamp_iso = datetime.datetime.now().isoformat()
    
    hwnd = win32gui.GetForegroundWindow()
    active_window = get_active_window_title(hwnd)
    clean_app_name = get_process_app_name(hwnd)

    should_log = is_current_app_tracked(active_window)
    
    with lock:
        current_keys = key_presses
        current_clicks = mouse_clicks
        current_moves = mouse_movements
        
        if should_log:
            key_presses = 0
            mouse_clicks = 0
            mouse_movements = 0

    if not should_log:
        print(f"Skipping log: '{active_window}' is not a tracked application.")
        return

    time_since_last_activity = now - last_activity_time
    
    if time_since_last_activity >= IDLE_THRESHOLD_SECONDS:
        is_idle_detected = True

    if is_idle_detected:
        if current_keys >= WAKE_KEYS or \
           current_moves >= WAKE_MOVES or \
           current_clicks >= WAKE_CLICKS:
            is_idle_detected = False
            last_activity_time = now
            
    is_idle = is_idle_detected
    
    log_payload = {
        "timestamp": timestamp_iso,
        "app": clean_app_name,
        "window": active_window,
        "keys": current_keys,
        "clicks": current_clicks,
        "movements": current_moves,
        "idle": is_idle,
    }

    try:
        response = requests.post("http://127.0.0.1:8000/api/logs/", json=log_payload, timeout=5)
        if response.status_code == 201:
            print(f"Successfully sent log to backend.")
        else:
            print(f"Failed to send log. Status: {response.status_code}, Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not send data to backend: {e}")

# --- Main Execution Block ---

if __name__ == "__main__":
    print("--- Simple Activity Tracker Started ---")
    print(f"Sending activity logs to the backend every {LOG_INTERVAL_SECONDS} seconds.")
    print(f"Idle threshold is set to {IDLE_THRESHOLD_SECONDS} seconds.")
    print(f"Tracking the following applications: {', '.join(TRACKED_APPS)}")
    print("Press Ctrl+C to stop the script.")
    
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    keyboard_listener.daemon = True
    keyboard_listener.start()
    print("Keyboard Listener started...")

    mouse_listener = mouse.Listener(on_click=on_mouse_click, on_move=on_mouse_move)
    mouse_listener.daemon = True
    mouse_listener.start()
    print("Mouse Listener started...")

    try:
        while True:
            log_activity()
            time.sleep(LOG_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\nStopping listeners...")
        keyboard_listener.stop()
        mouse_listener.stop()
        print("Tracker stopped.")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
