# ===========================
# Agent Configuration
# ===========================

# Unique ID for the employee (set this per machine)
EMPLOYEE_ID = "emp_123"

# Backend server endpoint (FastAPI ingest endpoint)
BACKEND_URL = "http://localhost:8000/ingest"

# Authentication token for secure communication with backend
API_KEY = "PUT_API_KEY_HERE"

# Idle threshold (in seconds)
IDLE_SECONDS = 120  # 2 minutes

# Aggregation interval (how often to save logs in seconds)
AGG_INTERVAL = 60   # 1 minute

# How often to send logs to backend (in seconds)
SEND_INTERVAL = 60  # 1 minute

# List of editing apps considered productive
EDITING_APPS = {
    "Premiere Pro",
    "After Effects",
    "Final Cut",
    "DaVinci Resolve",
    "Photoshop"
}
