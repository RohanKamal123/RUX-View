# ----------------------------------------------------------------------
# Python Activity Tracker for Windows
# Requires the following libraries:
# pip install pynput pywin32
# ----------------------------------------------------------------------

import time
import threading
import datetime
import json          # Added for structured JSON logging
import win32gui      # Used for getting the active window handle and title
import win32process  # NEW: Used for getting the process ID (PID)
import win32api      # NEW: Used for opening and closing the process handle
import os 

from pynput import keyboard
from pynput import mouse

# --- Configuration ---
# Logs activity every 10 seconds
LOG_INTERVAL_SECONDS = 10
# Idle threshold: 2 minutes (120 seconds)
IDLE_THRESHOLD_SECONDS = 120

# Static user ID for structured logs (change this to configure the user)
USER_ID = "EMP001" 

# --- Delayed Activation Thresholds ---
# Minimum inputs required in one 10-second interval to break an IDLE state.
WAKE_KEYS = 2
WAKE_MOVES = 3
WAKE_CLICKS = 1

# List of application names (or partial titles) to monitor
# Note: Titles are matched case-insensitively using the 'in' operator.
TRACKED_APPS = ["Visual Studio Code", "Thonny", "Chrome", "Telegram"] 

# --- Global Counters for Activity ---
key_presses = 0
mouse_clicks = 0
mouse_movements = 0
# Stores the timestamp of the last keyboard or mouse input that occurred in a TRACKED_APP
last_activity_time = time.time() 

# --- Global Variables for Idle State ---
# Flag that is set to True when the script detects the user has passed the IDLE_THRESHOLD_SECONDS.
is_idle_detected = False

lock = threading.Lock() # A lock to ensure safe access to shared counters

# --- 3. Active Window Tracker and Tracking Utilities ---

def get_log_filepath(extension=".txt"):
    """
    Generates the log file path based on the current date and specified extension.
    This ensures a new file is created automatically each day.
    """
    # Format the current date as YYYY-MM-DD
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    # Construct the filename
    return f"activity_{today_date}{extension}"

def get_process_app_name(hwnd):
    """
    NEW: Retrieves the actual application executable name (e.g., 'Chrome') 
    from the window handle (hwnd).
    """
    if not hwnd:
        return "N/A"
    
    try:
        # Get the process ID (PID) from the window handle
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        
        # Define access rights (PROCESS_QUERY_INFORMATION is sufficient for getting the path)
        PROCESS_QUERY_INFORMATION = 0x0400
        process_handle = win32api.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
        
        # Get the path of the executable
        executable_path = win32process.GetModuleFileNameEx(process_handle, 0)
        win32api.CloseHandle(process_handle)
        
        # Extract just the filename (e.g., 'chrome.exe')
        process_filename = os.path.basename(executable_path)
        
        # Clean the name: remove '.exe' (if present) and capitalize
        app_name = process_filename.rsplit('.', 1)[0]
        return app_name.capitalize()
    except Exception:
        # Fallback if process info cannot be retrieved (e.g., system process or permission denied)
        return "Unknown_App"

def get_active_window_title(hwnd):
    """Uses pywin32 to get the title of the currently focused window using its handle."""
    try:
        # Get the title of that window
        title = win32gui.GetWindowText(hwnd)
        return title if title else "N/A (Desktop/Unknown)"
    except Exception as e:
        return f"Error fetching window title: {e}"

def is_current_app_tracked(active_window_title):
    """
    Checks if the active window title contains any of the TRACKED_APPS names (case-insensitive).
    (Note: This tracking logic still uses the title for flexibility, as the executable name 
    might not always match the common application name in the TRACKED_APPS list.)
    """
    if not active_window_title:
        return False
    
    # Normalize the title for comparison
    normalized_title = active_window_title.lower()
    
    # Check if the normalized title contains any of the tracked app names
    return any(app.lower() in normalized_title for app in TRACKED_APPS)


# --- 1. Keyboard Listener Callbacks ---

def on_key_press(key):
    """
    Callback function executed every time a key is pressed.
    Updates main counter and updates last_activity_time only if the user is NOT idle
    and the activity is in a tracked app.
    """
    global key_presses, last_activity_time, is_idle_detected
    with lock:
        key_presses += 1
        
        # Get the window handle and title to check if the app is tracked
        hwnd = win32gui.GetForegroundWindow()
        window_title = get_active_window_title(hwnd)
        is_tracked = is_current_app_tracked(window_title)
        
        if not is_tracked:
            return

        # If we are NOT idle, any input in a tracked app immediately resets the timer
        if not is_idle_detected:
            last_activity_time = time.time()

# --- 2. Mouse Listener Callbacks ---

def on_mouse_click(x, y, button, pressed):
    """
    Callback function executed every time the mouse is clicked.
    Updates main counter and updates last_activity_time only if the user is NOT idle
    and the activity is in a tracked app.
    """
    global mouse_clicks, last_activity_time, is_idle_detected
    if pressed:
        with lock:
            mouse_clicks += 1
            
            # Get the window handle and title to check if the app is tracked
            hwnd = win32gui.GetForegroundWindow()
            window_title = get_active_window_title(hwnd)
            is_tracked = is_current_app_tracked(window_title)
            
            # Only update last_activity_time if we are NOT already idle AND in a tracked app.
            if not is_idle_detected and is_tracked:
                last_activity_time = time.time()

def on_mouse_move(x, y):
    """
    Callback function executed every time the mouse is moved.
    Updates main counter and updates last_activity_time only if the user is NOT idle
    and the activity is in a tracked app.
    """
    global mouse_movements, last_activity_time, is_idle_detected
    
    with lock:
        # Get the window handle and title to check if the app is tracked
        hwnd = win32gui.GetForegroundWindow()
        window_title = get_active_window_title(hwnd)
        is_tracked = is_current_app_tracked(window_title)

        # If NOT idle AND activity is in a tracked app, reset timer
        if not is_idle_detected and is_tracked:
            last_activity_time = time.time()
        
        # Movement counting for logging purposes (regardless of idle state)
        # We only count every 10 events to prevent the counter from growing too fast.
        if mouse_movements % 10 == 0:
            mouse_movements += 1

    # Note: Returning False from a listener callback stops the listener.
    return True

# --- 4. Logging Function and Counter Reset (with Process Name logic) ---

def log_activity():
    """
    Collects current data, determines idle state, checks for re-activation, 
    writes it to the log file (TXT and JSON), and resets counters ONLY if a tracked app was active.
    """
    global key_presses, mouse_clicks, mouse_movements, last_activity_time, is_idle_detected

    # Get the current time for calculations and strings
    now = time.time()
    timestamp_iso = datetime.datetime.now().isoformat() # ISO format for structured data
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get the active window handle
    hwnd = win32gui.GetForegroundWindow()
    # Get the full window title
    active_window = get_active_window_title(hwnd)
    # NEW: Get the clean executable/process name
    clean_app_name = get_process_app_name(hwnd) 

    # --- Tracking Check ---
    should_log = is_current_app_tracked(active_window)
    
    # Safely extract and reset the global counters inside the lock
    with lock:
        current_keys = key_presses
        current_clicks = mouse_clicks
        current_moves = mouse_movements
        
        # --- COUNTER RESET LOGIC ---
        # Reset counters ONLY IF we are logging the activity (i.e., in a tracked app).
        if should_log:
            key_presses = 0
            mouse_clicks = 0
            mouse_movements = 0
        # ---------------------------

    # If the app is not tracked, we skip logging the interval
    if not should_log:
        print(f"Skipping log at {timestamp_str}: '{active_window}' is not a tracked application.")
        return # Exit early

    # --- IDLE and WAKE-UP LOGIC ---
    time_since_last_activity = now - last_activity_time
    
    # 1. Check for Idle state transition (Active -> Idle)
    if time_since_last_activity >= IDLE_THRESHOLD_SECONDS:
        is_idle_detected = True

    # 2. Check for Wake state transition (Idle -> Active)
    # This logic only executes if we are currently marked as idle
    if is_idle_detected:
        
        # Check if the activity (captured in the current 10-second interval) is enough to break the idle state
        if current_keys >= WAKE_KEYS or \
           current_moves >= WAKE_MOVES or \
           current_clicks >= WAKE_CLICKS:
            
            # Re-activation successful!
            is_idle_detected = False
            last_activity_time = now # Reset timer to now
            
    # The logged idle status is determined by the final flag value
    is_idle = is_idle_detected 
    
    # --- LOGGING ---
    
    # 1. Human-Readable Text Log
    current_text_file = get_log_filepath(".txt") # Get the .txt file path
    # NOTE: App field now uses the process name, and Window field uses the full title.
    text_log_entry = (
        f"[{timestamp_str}] | "
        f"App: '{clean_app_name}' | " 
        f"Window: '{active_window}' | "
        f"Keys: {current_keys} | "
        f"Clicks: {current_clicks} | "
        f"Movements: {current_moves} | "
        f"Idle: {is_idle}"
    )
    
    # 2. Structured JSON Log
    json_entry = {
        "timestamp": timestamp_iso, # ISO format
        "user_id": USER_ID, 
        "app_name": clean_app_name,
        "window_title": active_window,
        "keys": current_keys,
        "clicks": current_clicks,
        "movements": current_moves,
        "idle": is_idle
    }
    current_json_file = get_log_filepath(".json") # Get the .json file path

    try:
        # Write Human-readable log (append mode)
        with open(current_text_file, "a") as f:
            f.write(text_log_entry + "\n")

        # Write Structured JSON log (one object per line, append mode)
        with open(current_json_file, "a") as f:
            f.write(json.dumps(json_entry) + "\n")
            
        print(f"Logged to {current_text_file} (Text) and {current_json_file} (JSON).")

    except Exception as e:
        # This error message is crucial for debugging file write issues!
        print(f"ERROR: Could not write to log files: {e}")

# --- 5. Main Execution Block ---

if __name__ == "__main__":
    # Calculate the expected file path for today
    initial_log_file_txt = get_log_filepath(".txt")
    
    # Use os.path.join and os.getcwd to show the absolute path where the file should appear
    full_log_path_txt = os.path.join(os.getcwd(), initial_log_file_txt)

    print("--- Simple Activity Tracker Started ---")
    # Tell the user exactly where to look for the files
    print(f"Log files are being created in the current directory: {os.getcwd()}") 
    print(f"Today's TEXT log is expected at: {full_log_path_txt}") 
    print(f"Today's JSON log is expected at: {os.path.join(os.getcwd(), get_log_filepath('.json'))}")
    print(f"Logging activity every {LOG_INTERVAL_SECONDS} seconds to date-based files (e.g., activity_YYYY-MM-DD.txt/.json).")
    print(f"Idle threshold is set to {IDLE_THRESHOLD_SECONDS} seconds (2 minutes).")
    print(f"Waking from Idle requires: {WAKE_KEYS}+ keys, {WAKE_MOVES}+ moves, or {WAKE_CLICKS}+ click(s) in a single interval.")
    print(f"Tracking the following applications: {', '.join(TRACKED_APPS)}")
    print(f"Structured logs use USER_ID: {USER_ID}")
    print("App Name is now based on the executable name (e.g., 'Chrome' from 'chrome.exe').")
    print("Press Ctrl+C to stop the script.")
    
    # 1. Start the keyboard listener thread
    # Setting 'daemon=True' ensures the listener thread terminates when the main script ends.
    keyboard_listener = keyboard.Listener(on_press=on_key_press)
    keyboard_listener.daemon = True
    keyboard_listener.start()
    print("Keyboard Listener started...")

    # 2. Start the mouse listener thread
    mouse_listener = mouse.Listener(on_click=on_mouse_click, on_move=on_mouse_move)
    mouse_listener.daemon = True
    mouse_listener.start()
    print("Mouse Listener started...")

    # 3. Main Loop for Periodic Logging
    try:
        while True:
            # Call the logging function
            log_activity()
            # Wait for the next interval
            time.sleep(LOG_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        # Stop listeners gracefully when the user presses Ctrl+C
        print("\nStopping listeners...")
        keyboard_listener.stop()
        mouse_listener.stop()
        print("Tracker stopped. Final activity logged.")
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
