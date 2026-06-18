# Vision OS V2 — DeepSeek Coding Prompts
# Copy-paste these prompts into DeepSeek to generate each sprint's code
# Each prompt includes: context + function signatures + test cases

---

## How to Use

1. Open DeepSeek (chat.deepseek.com)
2. Copy the entire prompt block for the sprint you want
3. Paste into DeepSeek
4. DeepSeek will generate: code + tests + docstring
5. Save the generated files to the correct paths
6. Run `pytest` to verify tests pass
7. Commit with `git commit -m "feat: [module] what it does"`

---

## SPRINT 2.1 — RTSP Reader + Frame Selector
### Files: connect/camera/rtsp_reader.py, connect/camera/frame_selector.py
### Tests: connect/tests/test_camera.py

```
You are building the client agent camera module for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: opencv-python (cv2) for RTSP + frame processing
- Client agent runs on Windows PC at customer premises
- Connects to local IP cameras via RTSP
- No continuous streaming — trigger-only architecture (D005)
- All connections are outbound only (solves NAT — D009)
- Frame selector picks best frame from N-frame burst

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)
- D009: Client agent solves NAT (outbound only)

FUNCTIONS TO IMPLEMENT (rtsp_reader.py):
```python
import cv2
import asyncio
from typing import Optional

class RTSPReader:
    """Manages RTSP connection to IP camera with auto-reconnect."""

    def __init__(self, rtsp_url: str, camera_id: str, reconnect_delay: int = 5):
        """Initialize RTSP reader.
        Args:
            rtsp_url: Full RTSP URL (e.g. rtsp://admin:pass@192.168.1.100:554/stream1)
            camera_id: Unique camera identifier
            reconnect_delay: Seconds to wait between reconnection attempts
        """

    async def connect(self) -> bool:
        """Open RTSP connection with cv2.VideoCapture.
        Returns: True if connection successful
        """

    async def read_frame(self) -> Optional[bytes]:
        """Read a single frame from RTSP stream.
        Returns: JPEG bytes or None if failed
        """

    async def read_burst(self, n_frames: int = 8) -> list[bytes]:
        """Read N consecutive frames as fast as possible.
        Returns: List of JPEG byte arrays
        """

    async def reconnect(self) -> bool:
        """Attempt reconnection with exponential backoff.
        Max retries: 5, then raise ConnectionError
        """

    async def disconnect(self) -> None:
        """Release VideoCapture resource."""

    @property
    def is_connected(self) -> bool:
        """Check if camera is currently connected."""
```

FUNCTIONS TO IMPLEMENT (frame_selector.py):
```python
import numpy as np

def select_best_frame(frames: list[bytes]) -> bytes:
    """Select the best frame from a burst of N frames.
    Scoring: largest person-shaped contour area wins.
    If no person contours found, pick frame with highest overall edge density.

    Args:
        frames: List of JPEG byte arrays (from read_burst)

    Returns:
        Best JPEG frame bytes
    """

def _score_frame(jpeg_bytes: bytes) -> float:
    """Score a frame by person-shaped contour area.
    1. Decode JPEG to numpy array
    2. Convert to grayscale
    3. Apply Canny edge detection
    4. Find contours
    5. Filter by aspect ratio (person-like: 0.3-1.5 width/height)
    6. Return sum of filtered contour areas
    """

def _person_aspect_ratio(contour) -> bool:
    """Check if contour aspect ratio matches a person (0.3-1.5)."""
```

TEST CASES TO WRITE (test_camera.py):
```python
test_rtsp_connection_local()
test_reconnect_on_drop()
test_frame_selector_picks_highest_score()
test_jpeg_encoding()
test_read_burst_returns_n_frames()
test_empty_frames_returns_none()
test_invalid_rtsp_url_raises_error()
```

OUTPUT: Generate rtsp_reader.py and frame_selector.py with all functions, proper error handling, reconnection logic, and test file. Use async/await throughout.
```

---

## SPRINT 2.2 — Motion Detector
### File: connect/camera/motion_detector.py
### Tests: connect/tests/test_motion.py

```
You are building the motion detection module for Vision OS Connect client agent.

CONTEXT:
- Stack: opencv-python (cv2)
- Runs locally on Windows PC at customer premises — NO API calls
- Pixel diff between consecutive frames
- Ignore zones mask out areas (e.g. trees, road)
- Contour filtering by area + aspect ratio
- Parameters vary by camera mode (indoor/outdoor/parking/mixed/shop)

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)
- D008: Five separate modes (not one-size-fits-all)

PIXEL DIFF THRESHOLDS BY MODE:
```python
THRESHOLDS = {
    "indoor":  {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "outdoor": {"skip": 800, "check": 4000, "gemma": 4000, "urgent": 10000},
    "parking": {"skip": 600, "check": 3500, "gemma": 3500, "urgent": 9000},
    "shop":    {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "night":   {"skip": 300, "check": 2000, "gemma": 2000, "urgent": 5000},
}
```

FUNCTIONS TO IMPLEMENT:
```python
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class MotionResult:
    should_trigger: bool
    pixel_diff: int
    largest_contour_area: int
    diff_category: str  # "skip" / "check" / "gemma" / "urgent"
    contour_count: int

class MotionDetector:
    """Pixel-diff based motion detector with zone masking."""

    def __init__(self, mode: str = "indoor", ignore_zones: list[list[int]] | None = None):
        """Initialize motion detector.
        Args:
            mode: Camera mode (indoor/outdoor/parking/shop)
            ignore_zones: List of [x, y, w, h] rectangles to ignore
        """

    async def process(self, frame_jpeg: bytes) -> MotionResult:
        """Process a frame and return motion analysis.
        1. Decode JPEG
        2. Apply ignore zone mask
        3. Compare with previous frame (pixel diff)
        4. Find contours in diff image
        5. Filter by area + aspect ratio
        6. Categorize diff level
        7. Store current frame as previous for next call
        """

    def apply_ignore_zones(self, frame: np.ndarray) -> np.ndarray:
        """Mask out ignore zones with black rectangles."""

    def _contour_filter(self, contours: list, min_area: int = 100) -> list:
        """Filter contours by minimum area."""

    def _aspect_ratio_filter(self, contour) -> bool:
        """Filter contours that look person-like (0.3-1.5 aspect ratio)."""

    def _categorize_diff(self, pixel_diff: int) -> str:
        """Categorize diff level based on mode thresholds."""

    def reset(self) -> None:
        """Clear previous frame (call when camera mode changes)."""
```

TEST CASES TO WRITE (test_motion.py):
```python
test_no_motion_returns_false()
test_large_motion_returns_true()
test_ignore_zone_masks_motion()
test_aspect_ratio_filters_wide_objects()
test_diff_categories_per_mode()
test_outdoor_higher_threshold()
test_contour_filter_min_area()
test_reset_clears_previous_frame()
```

OUTPUT: Generate motion_detector.py with MotionDetector class, MotionResult dataclass, all helper functions, and test file. Use async/await.
```

---

## SPRINT 2.3 — YAMNet Audio Detector
### Files: connect/audio/audio_capture.py, connect/audio/yamnet_detector.py
### Tests: connect/tests/test_audio.py

```
You are building the audio detection module for Vision OS Connect client agent.

CONTEXT:
- Stack: pyaudio (audio capture) + tensorflow (YAMNet model)
- Runs locally on Windows PC — NO API calls for detection
- YAMNet classifies 521 sound classes (glass breaking, gunshot, speech, etc.)
- Audio captured in 8-second chunks when RMS threshold exceeded
- Only sends to server for Whisper transcription if speech detected

KEY DECISIONS:
- D003: Groq Whisper-compatible API for Bangla transcription (server-side)
- YAMNet runs locally on client (free, on-device)

FUNCTIONS TO IMPLEMENT (audio_capture.py):
```python
import pyaudio
import wave
import numpy as np
from typing import Optional

class AudioCapture:
    """Capture audio chunks from microphone or camera audio line."""

    def __init__(self, device_index: int = 0, sample_rate: int = 16000,
                 chunk_duration: float = 8.0, rms_threshold: float = 0.02):
        """Initialize audio capture.
        Args:
            device_index: PyAudio device index
            sample_rate: Sample rate in Hz (YAMNet expects 16kHz)
            chunk_duration: Seconds per audio chunk
            rms_threshold: Minimum RMS amplitude to trigger capture
        """

    async def start_stream(self) -> bool:
        """Open PyAudio input stream."""

    async def read_chunk(self) -> Optional[np.ndarray]:
        """Read one chunk of audio data.
        Returns: numpy array of float32 samples, or None if below threshold
        """

    def _calculate_rms(self, audio_data: np.ndarray) -> float:
        """Calculate RMS amplitude of audio chunk."""

    async def stop_stream(self) -> None:
        """Close PyAudio stream."""

    @property
    def is_streaming(self) -> bool:
        """Check if audio stream is active."""
```

FUNCTIONS TO IMPLEMENT (yamnet_detector.py):
```python
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from typing import Optional

# YAMNet class IDs of interest for security
SECURITY_CLASSES = {
    0: "speech",        # Speech
    1: "speech",        # Male speech
    2: "speech",        # Female speech
    380: "glass_breaking",
    381: "gunshot",
    382: "gunshot",
    400: "scream",
    401: "scream",
    402: "shout",
    403: "shout",
    404: "shout",
    420: "vehicle_alarm",
    421: "vehicle_alarm",
    422: "vehicle_horn",
    423: "vehicle_horn",
    424: "door_slam",
    425: "door_slam",
    426: "footsteps",
    427: "footsteps",
    428: "footsteps",
    429: "footsteps",
    430: "engine",
    431: "engine",
    432: "engine_idling",
    433: "engine_idling",
}

@dataclass
class YAMNetResult:
    class_name: str
    class_id: int
    confidence: float
    should_send_to_whisper: bool  # True if speech detected
    should_trigger: bool          # True if security-relevant sound

class YAMNetDetector:
    """YAMNet sound classifier for security-relevant audio events."""

    def __init__(self, speech_threshold: float = 0.5,
                 security_threshold: float = 0.3):
        """Initialize YAMNet model.
        Args:
            speech_threshold: Confidence threshold for speech detection
            security_threshold: Confidence threshold for security sounds
        """

    def load_model(self) -> None:
        """Load YAMNet model from tensorflow-hub.
        Model URL: 'https://tfhub.dev/google/yamnet/1'
        Lazy-loaded on first use.
        """

    async def classify(self, audio_chunk: np.ndarray) -> YAMNetResult:
        """Classify audio chunk using YAMNet.
        Args:
            audio_chunk: Float32 numpy array of audio samples (16kHz)
        Returns:
            YAMNetResult with top class and metadata
        """

    def _get_top_class(self, scores: np.ndarray, embeddings: np.ndarray,
                       spectrogram: np.ndarray) -> tuple[str, int, float]:
        """Get the highest-confidence class across all frames."""

    def _should_trigger(self, class_id: int, confidence: float) -> bool:
        """Check if this sound class should trigger an alert."""
```

TEST CASES TO WRITE (test_audio.py):
```python
test_silence_below_threshold()
test_loud_sound_above_threshold()
test_yamnet_classifies_glass_breaking()
test_yamnet_classifies_speech()
test_confidence_threshold_gates_whisper()
test_audio_capture_reads_chunk()
test_rms_calculation()
test_security_class_mapping()
```

OUTPUT: Generate audio_capture.py and yamnet_detector.py with all functions, proper error handling, and test file. Use async/await where appropriate.
```

---

## SPRINT 2.4 — Transport + Buffer
### Files: connect/transport/websocket_client.py, connect/transport/trigger_sender.py, connect/transport/sms_sender.py, connect/buffer/local_queue.py
### Tests: connect/tests/test_transport.py

```
You are building the transport and offline buffer module for Vision OS Connect client agent.

CONTEXT:
- Stack: httpx (async HTTP), websockets (persistent connection), sqlite3 (local buffer)
- Persistent outbound WebSocket with 30s heartbeat
- HTTPS POST for trigger data (JPEG + audio + metadata)
- SQLite local queue for offline buffering (48hr TTL, max 500 events)
- SSL Wireless SMS fallback for HIGH alerts during internet outage
- All connections are outbound only (solves NAT — D009)

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)
- D009: Client agent solves NAT (outbound only)

FUNCTIONS TO IMPLEMENT (websocket_client.py):
```python
import asyncio
from typing import Optional, Callable
from dataclasses import dataclass

@dataclass
class WSConfig:
    server_url: str  # wss://api.visionos.app/ws
    heartbeat_interval: int = 30
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 10

class WebSocketClient:
    """Persistent WebSocket connection to backend."""

    def __init__(self, config: WSConfig, camera_id: str, user_token: str):
        """Initialize WebSocket client."""

    async def connect(self) -> bool:
        """Establish WebSocket connection.
        Sends auth: {camera_id, token} on connect.
        """

    async def send_heartbeat(self) -> None:
        """Send heartbeat every 30s to keep connection alive."""

    async def send_message(self, message: dict) -> bool:
        """Send JSON message over WebSocket."""

    async def receive_messages(self, handler: Callable) -> None:
        """Continuously receive messages and pass to handler."""

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""

    async def reconnect(self) -> bool:
        """Reconnect with exponential backoff."""

    @property
    def is_connected(self) -> bool:
        """Check WebSocket connection status."""
```

FUNCTIONS TO IMPLEMENT (trigger_sender.py):
```python
import httpx
from typing import Optional

class TriggerSender:
    """Send JPEG + audio triggers to backend via HTTPS POST."""

    def __init__(self, backend_url: str, user_token: str):
        """Initialize trigger sender.
        Args:
            backend_url: Base URL of backend API
            user_token: Firebase ID token for auth
        """

    async def send_frame_trigger(self, jpeg_bytes: bytes,
                                  motion_result: dict,
                                  camera_id: str,
                                  timestamp: str) -> dict:
        """POST frame trigger to /triggers/frame.
        Returns: {status, incident_id}
        """

    async def send_audio_trigger(self, audio_bytes: bytes,
                                  yamnet_result: dict,
                                  camera_id: str,
                                  timestamp: str) -> dict:
        """POST audio trigger to /triggers/audio.
        Returns: {status, audio_event_id}
        """

    async def health_check(self) -> bool:
        """Check if backend is reachable (GET /health)."""
```

FUNCTIONS TO IMPLEMENT (sms_sender.py):
```python
class SMSSender:
    """SSL Wireless SMS fallback for HIGH alerts during outage."""

    def __init__(self, api_key: str, api_secret: str, sender_id: str):
        """Initialize SSL Wireless SMS client."""

    async def send_sms(self, phone: str, message: str) -> bool:
        """Send SMS via SSL Wireless API.
        Cost: ~0.30 BDT per SMS
        Only used for HIGH alerts during internet outage.
        """
```

FUNCTIONS TO IMPLEMENT (local_queue.py):
```python
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional

class LocalQueue:
    """SQLite-backed offline buffer for triggers."""

    def __init__(self, db_path: str = "visionos_queue.db",
                 max_events: int = 500, ttl_hours: int = 48):
        """Initialize local queue.
        Args:
            db_path: Path to SQLite database file
            max_events: Maximum events before dropping oldest
            ttl_hours: Time-to-live for queued events
        """

    def enqueue(self, trigger_data: dict) -> None:
        """Add trigger to queue.
        If queue is full, drop oldest event.
        """

    def dequeue_all(self) -> list[dict]:
        """Get all queued events (oldest first) and remove from queue."""

    def flush_to_server(self, sender: TriggerSender) -> int:
        """Send all queued events to backend.
        Returns: Number of successfully sent events
        Events are removed from queue after successful send.
        """

    def count(self) -> int:
        """Get number of events in queue."""

    def cleanup_expired(self) -> int:
        """Remove events older than TTL.
        Returns: Number of removed events
        """

    def close(self) -> None:
        """Close SQLite connection."""
```

TEST CASES TO WRITE (test_transport.py):
```python
test_trigger_sends_on_internet_up()
test_trigger_queues_on_internet_down()
test_queue_flushes_on_reconnect()
test_queue_drops_oldest_at_capacity()
test_sms_sends_for_high_threat_outage()
test_websocket_heartbeat()
test_websocket_reconnect_on_drop()
test_queue_cleanup_expired()
```

OUTPUT: Generate all 4 transport/buffer files with proper error handling, reconnection logic, and test file. Use async/await throughout.
```

---

## SPRINT 2.5 — Windows App Packaging
### Files: connect/main.py, connect/config.py, connect/ui/tray_app.py
### Tests: Manual (no automated tests for UI)

```
You are building the main entry point and Windows system tray app for Vision OS Connect client agent.

CONTEXT:
- Stack: Python + pystray (system tray) + tkinter (settings window)
- Nuitka compiles to single .exe (D025 — NOT PyInstaller)
- Config stored as JSON file in %APPDATA%/VisionOS/
- System tray icon shows running/stopped/error states
- Settings window: API key, camera name, RTSP URL, mode
- QR code scan to auto-fill API key (optional)

KEY DECISIONS:
- D025: Nuitka (NOT PyInstaller) — no antivirus false positives
- D009: Client agent solves NAT (outbound only)

FUNCTIONS TO IMPLEMENT (config.py):
```python
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", "."), "VisionOS")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

@dataclass
class AppConfig:
    api_key: str = ""
    camera_id: str = ""
    camera_name: str = ""
    rtsp_url: str = ""
    mode: str = "indoor"  # indoor/outdoor/parking/mixed/shop
    backend_url: str = "https://api.visionos.app"
    audio_enabled: bool = True
    auto_start: bool = False
    ignore_zones: list = None

    def __post_init__(self):
        if self.ignore_zones is None:
            self.ignore_zones = []

def load_config() -> AppConfig:
    """Load config from JSON file. Returns defaults if file doesn't exist."""

def save_config(config: AppConfig) -> None:
    """Save config to JSON file. Creates directory if needed."""

def config_exists() -> bool:
    """Check if config file exists."""
```

FUNCTIONS TO IMPLEMENT (main.py):
```python
import asyncio
import logging
from connect.config import AppConfig, load_config, save_config
from connect.camera.rtsp_reader import RTSPReader
from connect.camera.frame_selector import select_best_frame
from connect.camera.motion_detector import MotionDetector
from connect.audio.audio_capture import AudioCapture
from connect.audio.yamnet_detector import YAMNetDetector
from connect.transport.trigger_sender import TriggerSender
from connect.transport.local_queue import LocalQueue

class VisionOSConnect:
    """Main application class orchestrating all client modules."""

    def __init__(self, config: AppConfig):
        """Initialize all modules from config."""

    async def start(self) -> None:
        """Start all modules:
        1. Connect to RTSP camera
        2. Start audio capture
        3. Start motion detection loop
        4. On trigger: select frame, classify audio, send to backend
        5. If offline: queue locally
        """

    async def stop(self) -> None:
        """Gracefully stop all modules and cleanup."""

    async def _process_trigger(self, motion_result, audio_chunk=None) -> None:
        """Handle a motion trigger:
        1. Read burst of frames
        2. Select best frame
        3. Classify audio if available
        4. Send to backend (or queue if offline)
        """

    async def _main_loop(self) -> None:
        """Main processing loop:
        - Read frames continuously
        - Run motion detection
        - On trigger: process
        - Check for backend commands via WebSocket
        """

    @property
    def status(self) -> str:
        """Return current status: running/stopped/error."""
```

FUNCTIONS TO IMPLEMENT (tray_app.py):
```python
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import ttk
from typing import Optional

class TrayApp:
    """Windows system tray application."""

    def __init__(self, app: VisionOSConnect):
        """Initialize tray icon and menu."""

    def _create_icon(self, status: str) -> Image:
        """Create tray icon based on status.
        Green = running, Red = stopped, Yellow = error
        """

    def _build_menu(self):
        """Build right-click menu:
        - Open Settings
        - Start / Stop
        - Exit
        """

    def run(self) -> None:
        """Run the tray application (blocking)."""

    def stop(self) -> None:
        """Stop the tray application."""

class SettingsWindow:
    """Tkinter settings window for configuration."""

    def __init__(self, config: AppConfig):
        """Build settings window with fields:
        - API Key (with QR scan button)
        - Camera Name
        - RTSP URL
        - Camera Mode dropdown
        - Audio Enabled checkbox
        - Auto Start checkbox
        - Save button
        """

    def show(self) -> None:
        """Display the settings window."""

    def _on_save(self) -> None:
        """Validate and save settings."""
```

MANUAL TEST CHECKLIST (no automated tests):
```python
# Manual verification steps:
# [ ] Install on Windows PC
# [ ] Connect to real IP camera
# [ ] Verify trigger reaches backend
# [ ] Verify tray icon shows correct state
# [ ] Open settings, change config, verify saved
# [ ] Confirm Windows Defender does not flag the binary
# [ ] Test offline buffer (disconnect internet)
# [ ] Test buffer flush on reconnect
```

OUTPUT: Generate main.py, config.py, and tray_app.py with all functions, proper error handling, and manual test checklist. Use async/await throughout.
```

---

## SPRINT 3.1 — Incident Tracker
### File: backend/core/incident_tracker.py
### Tests: backend/tests/unit/test_incident_tracker.py

```
You are building the incident tracker state machine for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio
- One IncidentTracker instance per camera
- State machine: IDLE → TRACKING → CLOSE
- IDLE: Gemma OFF, cost $0
- TRACKING: Gemma ON, burst every 2.5s when behaviour changes
- CLOSE: Send full timeline to Gemini, route alert, save to DB
- Timing parameters vary by camera mode

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)
- D026: All calls async

STATE MACHINE:
```
IDLE → (motion passes filters + cooldown elapsed) → TRACKING → (no motion 3-6s) → CLOSE
```

TIMING PARAMETERS BY MODE:
```python
TIMING = {
    "indoor":  {"cooldown": 15, "burst": 2.5, "urgent": 0.8, "no_motion": 3, "max_cap": 60},
    "outdoor": {"cooldown": 30, "burst": 2.5, "urgent": 0.8, "no_motion": 6, "max_cap": 60},
    "parking": {"cooldown": 20, "burst": 2.5, "urgent": 0.8, "no_motion": 4, "max_cap": 120},
    "shop":    {"cooldown": 10, "burst": 2.5, "urgent": 0.8, "no_motion": 3, "max_cap": 300},
    "night":   {"cooldown": 8,  "burst": 1.5, "urgent": 0.8, "no_motion": 4, "max_cap": 60},
}
```

PIXEL DIFF THRESHOLDS:
```python
THRESHOLDS = {
    "indoor":  {"skip": 400, "check": 2500, "gemma": 2500, "urgent": 7000},
    "outdoor": {"skip": 800, "check": 4000, "gemma": 4000, "urgent": 10000},
    "parking": {"skip": 600, "check": 3500, "gemma": 3500, "urgent": 9000},
    "night":   {"skip": 300, "check": 2000, "gemma": 2000, "urgent": 5000},
}
```

LOITERING ESCALATION TIMERS:
```python
LOITER = {
    "front_gate":       {"low": 45, "medium": 120, "high": 240},
    "parking_others":   {"low": 45, "medium": 90, "high": 150},
    "parking_afterhrs": {"low": 15, "medium": 30, "high": 60},
    "indoor_general":   {"low": 60, "medium": 180, "high": 300},
}
```

FUNCTIONS TO IMPLEMENT:
```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

class CamState(Enum):
    IDLE = "idle"
    TRACKING = "tracking"
    CLOSE = "close"

class IncidentAction(Enum):
    GEMMA_CALL = "gemma_call"
    BURST = "burst"
    CLOSE_INCIDENT = "close_incident"
    NONE = "none"

@dataclass
class TriggerData:
    camera_id: str
    timestamp: datetime
    pixel_diff: int
    diff_category: str  # skip/check/gemma/urgent
    jpeg_bytes: Optional[bytes] = None
    audio_bytes: Optional[bytes] = None
    yamnet_result: Optional[dict] = None

@dataclass
class IncidentState:
    incident_id: str
    state: CamState = CamState.IDLE
    start_time: Optional[datetime] = None
    last_gemma_time: Optional[datetime] = None
    last_motion_time: Optional[datetime] = None
    last_loiter_escalation: str = "none"  # none/low/medium/high
    timeline: list = field(default_factory=list)
    burst_count: int = 0
    person_ids: list = field(default_factory=list)

class IncidentTracker:
    """Per-camera incident state machine."""

    def __init__(self, camera_id: str, mode: str = "indoor",
                 location_type: str = "indoor_general"):
        """Initialize tracker for a camera.
        Args:
            camera_id: Unique camera identifier
            mode: Camera mode (indoor/outdoor/parking/shop)
            location_type: For loiter params (front_gate/parking_others/etc)
        """

    async def process(self, trigger: TriggerData) -> IncidentAction:
        """Process a motion trigger through the state machine.
        Returns: IncidentAction indicating what the pipeline should do next.
        """

    def _transition_idle_to_tracking(self, trigger: TriggerData) -> IncidentAction:
        """IDLE → TRACKING: Start new incident, return GEMMA_CALL."""

    def _process_tracking(self, trigger: TriggerData) -> IncidentAction:
        """TRACKING state logic:
        - Check cooldown elapsed → GEMMA_CALL
        - Check urgent threshold → BURST (override cooldown)
        - Check no-motion timeout → CLOSE_INCIDENT
        - Check max cap duration → CLOSE_INCIDENT
        - Check loitering escalation
        """

    def _check_loiter_escalation(self) -> Optional[str]:
        """Check if loitering time has crossed escalation threshold.
        Returns: new escalation level or None
        """

    def _get_timing_params(self) -> dict:
        """Get timing parameters for current mode."""

    def _get_thresholds(self) -> dict:
        """Get pixel diff thresholds for current mode."""

    def reset(self) -> None:
        """Reset tracker to IDLE state."""

    @property
    def current_state(self) -> CamState:
        """Get current state."""

    @property
    def incident_duration(self) -> float:
        """Get incident duration in seconds."""
```

TEST CASES TO WRITE (test_incident_tracker.py):
```python
test_idle_transitions_to_tracking_on_trigger()
test_tracking_closes_on_no_motion()
test_burst_fires_at_correct_interval()
test_loitering_escalates_at_correct_times()
test_night_mode_halves_cooldown()
test_max_cap_closes_incident()
test_gemma_skip_on_no_change()
test_urgent_overrides_cooldown()
test_idle_ignores_low_diff()
test_loiter_front_gate_escalation_times()
```

OUTPUT: Generate incident_tracker.py with IncidentTracker class, all enums/dataclasses, state machine logic, and test file. Use async/await throughout.
```

---

## SPRINT 3.2 — Camera Modes
### Files: backend/modes/indoor_mode.py, outdoor_mode.py, parking_mode.py, mixed_mode.py, shop_mode.py
### Tests: backend/tests/unit/test_modes.py

```
You are building the camera mode modules for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Pure Python data + logic (no external dependencies)
- Five separate mode files, one per camera mode
- Each provides mode-specific parameters and detection logic
- Used by IncidentTracker and Pipeline

KEY DECISIONS:
- D008: Five separate modes (not one-size-fits-all)
- D017: MOG2 for outdoor (statistical, not per-person)
- D028: Gate line-crossing counter (centroid-based)

FUNCTIONS TO IMPLEMENT (each mode file):
```python
from dataclasses import dataclass

@dataclass
class MotionParams:
    skip_threshold: int
    check_threshold: int
    gemma_threshold: int
    urgent_threshold: int

@dataclass
class TimingParams:
    cooldown: int          # seconds between Gemma calls
    burst_interval: float  # seconds between burst frames
    urgent_interval: float # seconds between urgent frames
    no_motion_timeout: int # seconds before closing incident
    max_cap_duration: int  # max incident duration in seconds

@dataclass
class LoiterParams:
    low_seconds: int
    medium_seconds: int
    high_seconds: int

def get_motion_params(mode: str) -> MotionParams:
    """Get motion detection thresholds for the given mode.
    Returns: MotionParams with skip/check/gemma/urgent thresholds
    """

def get_timing_params(mode: str, is_night: bool = False) -> TimingParams:
    """Get timing parameters for the given mode.
    If is_night=True, cooldown is halved and burst is faster.
    Returns: TimingParams
    """

def get_loiter_params(mode: str, location_type: str) -> LoiterParams:
    """Get loitering escalation timers.
    Args:
        mode: Camera mode
        location_type: front_gate/parking_others/parking_afterhrs/indoor_general
    Returns: LoiterParams with low/medium/high thresholds in seconds
    """

def should_analyse_individual(mode: str, zone: str = None) -> bool:
    """Check if individual person analysis should be performed.
    Returns: True for indoor/parking, False for outdoor public zone
    """
```

MODE-SPECIFIC FUNCTIONS:

indoor_mode.py:
```python
def is_night_time(current_time, night_start="22:00", night_end="06:00") -> bool:
    """Check if current time is within night hours."""

def get_night_params() -> dict:
    """Get night-specific parameter overrides."""
```

outdoor_mode.py:
```python
def get_mog2_params() -> dict:
    """Get MOG2 background subtractor parameters.
    Returns: {history, varThreshold, detectShadows}
    """

def get_crowd_thresholds() -> dict:
    """Get crowd anomaly detection thresholds.
    Returns: {person_count_threshold, motion_density_threshold}
    """

def get_gate_line_crossing_params() -> dict:
    """Get gate line-crossing detection parameters.
    Returns: {line_coordinates, direction_tracking_enabled}
    """
```

parking_mode.py:
```python
def get_vehicle_detection_params() -> dict:
    """Get vehicle detection parameters.
    Returns: {min_vehicle_area, aspect_ratio_range, headlight_threshold}
    """

def is_night_time(current_time, night_start="22:00", night_end="06:00") -> bool:
    """Check if current time is within night hours."""

def get_night_params() -> dict:
    """Get night-specific parameter overrides for parking."""
```

mixed_mode.py:
```python
def get_zone_config() -> dict:
    """Get zone-based split configuration.
    Returns: {public_zone_coords, property_zone_coords, crossing_line}
    """

def is_crossing_public_to_property(track_history: list) -> bool:
    """Check if a person crossed from public zone to property zone."""

def get_public_zone_mode() -> str:
    """Returns 'outdoor' — public zone uses outdoor logic only."""
```

shop_mode.py:
```python
def get_business_hours(shop_hours_open: str, shop_hours_close: str) -> dict:
    """Get business hours configuration.
    Returns: {open, close, is_open_now}
    """

def is_staff_entrance(zone: str) -> bool:
    """Check if zone is a staff-only entrance."""

def get_after_hours_params() -> dict:
    """Get after-hours security mode parameters (same as night mode)."""
```

TEST CASES TO WRITE (test_modes.py):
```python
test_indoor_lower_thresholds_than_outdoor()
test_parking_vehicle_trigger_logic()
test_outdoor_mog2_baseline_learns()
test_mixed_zone_crossing_triggers()
test_shop_floor_loiter_disabled_business_hours()
test_night_mode_halves_cooldown()
test_should_analyse_individual_returns_false_for_outdoor()
test_loiter_params_by_location_type()
test_shop_business_hours_check()
test_parking_headlight_detection_at_night()
```

OUTPUT: Generate all 5 mode files with proper dataclasses, mode-specific functions, and test file. Each file max 200 lines.
```

---

## SPRINT 3.3 — Re-ID Engine
### File: backend/ai/reid_engine.py
### Tests: backend/tests/unit/test_reid_engine.py

```
You are building the Re-ID (Re-Identification) engine for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: boxmot (BoT-SORT + FastReID) for person embeddings
- pgvector in Postgres for cosine similarity search (D022)
- 512-dimension embeddings stored in persons.embedding column
- Three-tier matching: exact → pgvector similarity → AI tiebreaker
- Uncertainty zone: 0.5-0.72 cosine similarity → calls ai_client.reid_tiebreaker()

KEY DECISIONS:
- D007: BoxMOT (FastReID) — replaces torchreid, actively maintained
- D022: pgvector in Postgres — native vector similarity, no separate DB

MATCHING TIERS:
```
Tier 1: Exact match (same person_uid) → return existing
Tier 2: pgvector cosine similarity > 0.72 → auto-match
Tier 3: pgvector cosine similarity 0.5-0.72 → AI tiebreaker
         < 0.5 → new person
```

FUNCTIONS TO IMPLEMENT:
```python
import numpy as np
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

class ReIDEngine:
    """Person Re-Identification engine using FastReID + pgvector."""

    def __init__(self):
        """Initialize FastReID model (lazy-loaded)."""

    def _load_model(self) -> None:
        """Load FastReID model from boxmot.
        Lazy-loaded on first use.
        Uses FastReID backend with ResNet50.
        """

    async def extract_embedding(self, person_crop: np.ndarray) -> np.ndarray:
        """Extract 512-dimension embedding from a person crop.
        Args:
            person_crop: RGB numpy array of cropped person
        Returns:
            512-dim float32 numpy array
        """

    async def crop_person(self, frame: np.ndarray, bbox_normalized: list[float],
                           frame_width: int, frame_height: int) -> Optional[np.ndarray]:
        """Crop a person from frame using normalized bbox.
        Args:
            frame: Full frame numpy array
            bbox_normalized: [x1, y1, x2, y2] normalized 0-1
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
        Returns:
            Cropped RGB numpy array or None if bbox invalid
        """

    async def identify(self, db: AsyncSession, frame: np.ndarray,
                        person_result: dict, location_id: str,
                        user_id: str) -> tuple[str, float]:
        """Identify a person from a frame + AI analysis result.
        Args:
            db: Database session
            frame: Full frame numpy array
            person_result: Dict from ai_client.analyse_frame() for this person
            location_id: Location UUID
            user_id: User UUID
        Returns:
            (person_uid, confidence) — existing or new PERSON_XXX
        """

    async def find_similar(self, db: AsyncSession, embedding: list[float],
                            location_id: str, limit: int = 5) -> list[dict]:
        """Find similar persons using pgvector cosine similarity.
        Delegates to crud.find_similar_persons().
        """

    def appearance_signature(self, person_result: dict) -> str:
        """Generate a text signature from AI person analysis.
        Used for tiebreaker comparison.
        Format: "gender|clothing|hand_objects|action"
        """

    def string_similarity(self, sig_a: str, sig_b: str) -> float:
        """Compute simple string similarity between two appearance signatures.
        Uses token overlap (Jaccard-like).
        Returns: 0.0 to 1.0
        """
```

TEST CASES TO WRITE (test_reid_engine.py):
```python
test_same_person_different_frames_matches()
test_different_people_dont_match()
test_new_person_gets_new_id()
test_pgvector_similarity_query_returns_correct_person()
test_uncertain_zone_calls_ai_client_tiebreaker()
test_appearance_signature_format()
test_crop_person_valid_bbox()
test_crop_person_invalid_bbox_returns_none()
test_string_similarity_identical()
test_string_similarity_different()
```

OUTPUT: Generate reid_engine.py with ReIDEngine class, all helper functions, and test file. Use async/await throughout.
```

---

## SPRINT 3.4 — Cross-Camera + Ghost Detection
### Files: backend/core/cross_camera.py, backend/core/ghost_detector.py, backend/core/repeat_sighting.py
### Tests: backend/tests/unit/test_cross_camera.py

```
You are building the cross-camera correlation, ghost detection, and repeat sighting modules for Vision OS.

CONTEXT:
- Stack: Python asyncio + SQLAlchemy async
- Cross-camera: correlates person sightings across cameras within same location
- NEVER crosses location boundary (HARD RULE enforced in SQL)
- Ghost detection: alerts if person entered but not seen leaving (10min/30min)
- Repeat sighting: frequency escalation (1st=LOG, 2nd=LOW, 3rd=MEDIUM, 4th+=HIGH)
- Camera topology from user config

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)
- D026: All calls async

FUNCTIONS TO IMPLEMENT (cross_camera.py):
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class CrossCameraResult:
    matched: bool
    matched_person_uid: Optional[str] = None
    source_camera_id: Optional[str] = None
    time_gap_seconds: Optional[float] = None
    confidence: float = 0.0
    impossible_timing: bool = False

@dataclass
class GhostCheckResult:
    is_ghost: bool
    alert_level: Optional[str] = None  # MEDIUM / HIGH
    message: Optional[str] = None

class CrossCameraCorrelator:
    """Correlate person sightings across cameras within a location."""

    def __init__(self, db_session_factory):
        """Initialize with DB session factory."""

    async def correlate_across_cameras(self, person_uid: str,
                                        source_camera_id: str,
                                        location_id: str,
                                        event_timestamp: datetime,
                                        direction: str = "unknown") -> CrossCameraResult:
        """Check if this person was seen on another camera recently.
        Args:
            person_uid: Person identifier
            source_camera_id: Camera that just saw this person
            location_id: Location UUID (HARD boundary)
            event_timestamp: When the sighting occurred
            direction: Direction person was moving
        Returns:
            CrossCameraResult with match info
        """

    async def check_ghost_condition(self, person_uid: str,
                                      location_id: str,
                                      entry_camera_id: str,
                                      entry_timestamp: datetime) -> GhostCheckResult:
        """Check if a person who entered has not been seen leaving.
        Args:
            person_uid: Person identifier
            location_id: Location UUID
            entry_camera_id: Camera where person was first seen
            entry_timestamp: When person was first seen
        Returns:
            GhostCheckResult with alert info
        """

    def _get_neighbour_cameras(self, camera_id: str,
                                topology: dict) -> list[str]:
        """Get neighbouring cameras from topology config."""

    def _detect_impossible_timing(self, time_gap: float,
                                    cam_a: str, cam_b: str,
                                    topology: dict) -> bool:
        """Detect if a person appearing at cam_b too quickly after cam_a is impossible.
        Uses min_transit_time from topology config.
        """
```

FUNCTIONS TO IMPLEMENT (ghost_detector.py):
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class GhostAlert:
    person_uid: str
    camera_id: str
    timestamp: datetime
    alert_level: str  # MEDIUM / HIGH
    message: str
    dismissed: bool = False

class GhostDetector:
    """Detect persons who entered but haven't been seen leaving."""

    def __init__(self):
        """Initialize ghost detector with in-memory tracking."""

    async def track_entry(self, person_uid: str, camera_id: str,
                           location_id: str, timestamp: datetime) -> None:
        """Record a person entry for ghost tracking.
        Schedules checks at 10min (MEDIUM) and 30min (HIGH).
        """

    async def check_unaccounted(self) -> list[GhostAlert]:
        """Check all tracked entries that haven't been resolved.
        Returns: List of GhostAlerts that have crossed their threshold.
        """

    async def cancel_ghost(self, person_uid: str) -> bool:
        """Cancel ghost tracking for a person (seen leaving or dismissed).
        Returns: True if person was being tracked
        """

    async def record_exit(self, person_uid: str, camera_id: str,
                           timestamp: datetime) -> None:
        """Record a person exit to cancel ghost tracking."""
```

FUNCTIONS TO IMPLEMENT (repeat_sighting.py):
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class SightingRecord:
    person_uid: str
    user_id: str
    count_today: int = 0
    first_seen_today: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    escalation_level: str = "none"  # none/low/medium/high

class RepeatSightingTracker:
    """Track repeat sightings and escalate threat level."""

    def __init__(self):
        """Initialize tracker with in-memory state."""

    async def record_sighting(self, person_uid: str, user_id: str,
                               timestamp: datetime, is_night: bool = False) -> str:
        """Record a sighting and return escalation level.
        Escalation:
        - 1st: LOG only ("none")
        - 2nd: LOW alert
        - 3rd: MEDIUM + "seen X times today"
        - 4th: HIGH + emergency voice note
        - 5th+: HIGH every time
        Returns: escalation level string
        """

    async def get_today_count(self, person_uid: str, user_id: str) -> int:
        """Get number of sightings today for a person."""

    async def get_escalation_level(self, count: int, is_night: bool) -> str:
        """Get escalation level based on sighting count.
        Night hours (10pm-6am) escalate faster.
        """

    async def should_reset(self, person_uid: str, user_id: str,
                            last_seen: datetime, is_night: bool) -> bool:
        """Check if sighting count should reset.
        Reset conditions:
        - 6 hours no sighting → reset
        - Night hours NEVER reset
        - After hours at business NEVER reset
        """
```

TEST CASES TO WRITE (test_cross_camera.py):
```python
test_cross_camera_matches_within_window()
test_cross_camera_misses_outside_window()
test_impossible_timing_flagged()
test_ghost_alert_fires_at_10_min()
test_ghost_alert_fires_at_30_min()
test_ghost_cancelled_on_sighting()
test_repeat_escalation_1st_to_4th()
test_repeat_resets_after_6_hours()
test_repeat_never_resets_at_night()
test_cross_camera_never_crosses_location()
```

OUTPUT: Generate cross_camera.py, ghost_detector.py, and repeat_sighting.py with all classes, dataclasses, and test file. Use async/await throughout.
```

---

## SPRINT 3.5 — Alert Router + Telegram
### Files: backend/alerts/alert_router.py, backend/alerts/telegram_client.py, backend/alerts/voice_note.py, backend/alerts/sms_client.py
### Tests: backend/tests/unit/test_alerts.py

```
You are building the alert routing and delivery modules for Vision OS.

CONTEXT:
- Stack: httpx (async HTTP), python-telegram-bot or raw HTTP, kokoro (TTS), ffmpeg
- Four files handling all alert delivery channels
- Routing by threat level: LOW→log, MEDIUM→text, HIGH→photo, EMERGENCY→voice
- Retry logic: 90s intervals, max 3 attempts
- Secondary contact escalation on no response
- Plain text format (NO markdown — timestamp underscores break markdown)

KEY DECISIONS:
- D023: Kokoro-82M (NOT gTTS/pyttsx3) — natural-sounding voice
- D014: Free tier gets digest (conversion hook)

ROUTING LOGIC:
```
LOW:      → Dashboard only, no Telegram
MEDIUM:   → Telegram text message
HIGH:     → Telegram photo + caption
EMERGENCY:→ Telegram urgent message + voice note
            Retry every 90s, max 3 attempts
            If no response → secondary contact
            If still no response → log as unacknowledged

During internet outage (HIGH only):
          → SSL Wireless SMS (~0.30 BDT)
```

FUNCTIONS TO IMPLEMENT (alert_router.py):
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class AlertAction:
    channel: str  # "log" / "telegram_text" / "telegram_photo" / "telegram_voice" / "sms"
    message: str
    jpeg_bytes: Optional[bytes] = None
    retry_count: int = 0
    acknowledged: bool = False

class AlertRouter:
    """Route alerts by threat level + user tier."""

    def __init__(self, telegram_client, voice_note_generator, sms_client):
        """Initialize with delivery channel clients."""

    async def route_alert(self, incident: dict, user: dict, tier: str) -> AlertAction:
        """Route an alert based on threat level and user tier.
        Args:
            incident: Dict with threat_level, alert_message, person_ids, timeline, jpeg_bytes
            user: User dict with telegram_chat_id, secondary_contact, etc.
            tier: User tier (free/household/business)
        Returns:
            AlertAction with delivery result
        """

    async def _route_low(self, incident: dict) -> AlertAction:
        """LOW: Log only, no Telegram."""

    async def _route_medium(self, incident: dict, user: dict) -> AlertAction:
        """MEDIUM: Telegram text message."""

    async def _route_high(self, incident: dict, user: dict) -> AlertAction:
        """HIGH: Telegram photo + caption."""

    async def _route_emergency(self, incident: dict, user: dict) -> AlertAction:
        """EMERGENCY: Telegram urgent + voice note + retry logic."""

    async def _retry_with_escalation(self, send_func, incident: dict,
                                      user: dict) -> AlertAction:
        """Retry delivery with secondary contact escalation."""
```

FUNCTIONS TO IMPLEMENT (telegram_client.py):
```python
class TelegramClient:
    """Telegram Bot API client for sending alerts."""

    def __init__(self, bot_token: str):
        """Initialize Telegram bot.
        Args:
            bot_token: Bot token from @BotFather
        """

    async def send_text(self, chat_id: str, message: str) -> bool:
        """Send plain text message.
        NO markdown formatting (timestamp underscores break markdown).
        Returns: True if sent successfully
        """

    async def send_photo(self, chat_id: str, jpeg_bytes: bytes,
                          caption: str) -> bool:
        """Send photo with caption.
        Returns: True if sent successfully
        """

    async def send_voice(self, chat_id: str, ogg_bytes: bytes,
                          caption: str) -> bool:
        """Send voice note (OGG Opus) with caption.
        Returns: True if sent successfully
        """

    def _format_medium_message(self, camera_name: str, timestamp: str,
                                description: str) -> str:
        """Format MEDIUM alert message.
        Format:
        VisionOS MEDIUM - {camera_name} - {timestamp}
        {description}
        Camera: {camera_name}
        """

    def _format_high_message(self, camera_name: str, timestamp: str,
                              description: str) -> str:
        """Format HIGH alert message.
        Format:
        VisionOS HIGH ALERT - {camera_name} - {timestamp}
        {description}
        """

    def _format_emergency_message(self, camera_name: str, timestamp: str,
                                   description: str, sighting_count: int) -> str:
        """Format EMERGENCY alert message.
        Format:
        VisionOS EMERGENCY - {camera_name} - {timestamp}
        {description}
        {sighting_count}th sighting today
        """
```

FUNCTIONS TO IMPLEMENT (voice_note.py):
```python
class VoiceNoteGenerator:
    """Generate emergency voice notes using Kokoro-82M TTS."""

    def __init__(self):
        """Initialize Kokoro TTS pipeline (lazy-loaded).
        Uses KPipeline(lang_code='a') for American English.
        """

    def _load_pipeline(self) -> None:
        """Load Kokoro TTS pipeline on first use."""

    async def generate_voice_note(self, camera_name: str, timestamp: str,
                                    threat_summary: str) -> bytes:
        """Generate an emergency voice note.
        Text template: "{camera_name}. {timestamp}. {threat_summary}."
        Returns: OGG Opus bytes for Telegram
        Steps:
        1. Generate WAV from Kokoro
        2. Convert WAV → OGG Opus via ffmpeg
        3. Return OGG bytes
        """

    def _text_to_wav(self, text: str) -> bytes:
        """Convert text to WAV audio using Kokoro."""

    def _wav_to_ogg(self, wav_bytes: bytes) -> bytes:
        """Convert WAV to OGG Opus using ffmpeg."""
```

FUNCTIONS TO IMPLEMENT (sms_client.py):
```python
class SMSClient:
    """SSL Wireless SMS client for emergency fallback."""

    def __init__(self, api_key: str, api_secret: str, sender_id: str):
        """Initialize SSL Wireless SMS client.
        Args:
            api_key: SSL Wireless API key
            api_secret: SSL Wireless API secret
            sender_id: SMS sender ID (approved)
        """

    async def send_sms(self, phone: str, message: str) -> bool:
        """Send SMS via SSL Wireless API.
        Cost: ~0.30 BDT per SMS
        Only used for HIGH alerts during internet outage.
        Returns: True if sent successfully
        """
```

TEST CASES TO WRITE (test_alerts.py):
```python
test_low_threat_logs_only()
test_medium_sends_telegram_text()
test_high_sends_telegram_photo()
test_emergency_sends_voice_note()
test_voice_note_returns_ogg_bytes()
test_plain_text_no_markdown()
test_retry_on_telegram_failure()
test_secondary_contact_escalation()
test_sms_sends_for_high_outage()
test_alert_format_messages()
```

OUTPUT: Generate all 4 alert files with proper classes, message formatting, retry logic, and test file. Use async/await throughout.
```

---

## SPRINT 3.6 — Pipeline Orchestrator
### File: backend/core/pipeline.py
### Tests: backend/tests/unit/test_pipeline.py

```
You are building the main pipeline orchestrator for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Python asyncio + FastAPI background tasks
- One CameraPipeline instance per camera
- Orchestrates the entire incident flow:
  incident_tracker → gemma → reid → cross_camera → repeat_sighting → ghost_detector → gemini_decision → alert_router → database
- All calls async, use asyncio.gather() for parallel AI calls (D026)
- Trigger-only architecture (D005)

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)
- D026: All calls async, use asyncio.gather() for parallel AI calls

ORCHESTRATION FLOW:
```
process_trigger(jpeg, audio, meta)
  → incident_tracker.process()
  → if GEMMA_CALL: ai_client.analyse_frame()
  → if person: reid_engine.get_or_create_person()
  → cross_camera.correlate_across_cameras()
  → repeat_sighting.record_sighting()
  → ghost_detector.track_entry()
  → ai_client.make_incident_decision()
  → alert_router.route_alert()
  → database.save_event()
```

FUNCTIONS TO IMPLEMENT:
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass
class PipelineContext:
    camera_id: str
    user_id: str
    location_id: str
    mode: str
    timestamp: datetime
    jpeg_bytes: Optional[bytes] = None
    audio_bytes: Optional[bytes] = None
    motion_result: Optional[dict] = None
    yamnet_result: Optional[dict] = None

@dataclass
class PipelineResult:
    incident_id: Optional[str] = None
    threat_level: str = "LOW"
    alert_sent: bool = False
    person_ids: list = field(default_factory=list)
    error: Optional[str] = None

class CameraPipeline:
    """Main pipeline orchestrator for a single camera."""

    def __init__(self, camera_id: str, user_id: str, location_id: str,
                 mode: str = "indoor", db_session_factory=None):
        """Initialize pipeline with all sub-modules.
        Creates:
        - IncidentTracker
        - ReIDEngine (shared singleton)
        - CrossCameraCorrelator
        - GhostDetector
        - RepeatSightingTracker
        - AlertRouter
        """

    async def process_trigger(self, ctx: PipelineContext) -> PipelineResult:
        """Process a trigger through the full pipeline.
        Args:
            ctx: PipelineContext with trigger data
        Returns:
            PipelineResult with incident outcome
        Steps:
        1. Run incident_tracker.process()
        2. If GEMMA_CALL: analyse frame with ai_client
        3. If persons found: run Re-ID
        4. Run cross-camera correlation
        5. Record repeat sighting
        6. Track ghost entry
        7. Make incident decision with ai_client
        8. Route alert
        9. Save event to database
        """

    async def _run_vision_analysis(self, ctx: PipelineContext) -> dict:
        """Run Gemini vision analysis on the frame."""

    async def _run_reid(self, frame: bytes, person_results: list,
                         ctx: PipelineContext) -> list[str]:
        """Run Re-ID on all detected persons.
        Returns: List of person_uid strings
        """

    async def _make_decision(self, timeline: list, ctx: PipelineContext,
                              person_ids: list) -> dict:
        """Make incident decision with Gemini."""

    async def _route_and_save(self, decision: dict, ctx: PipelineContext,
                               person_ids: list) -> PipelineResult:
        """Route alert and save event to database."""

    async def shutdown(self) -> None:
        """Clean shutdown of all sub-modules."""
```

TEST CASES TO WRITE (test_pipeline.py):
```python
test_full_indoor_incident_low()
test_full_indoor_incident_high()
test_full_parking_incident()
test_audio_visual_correlation()
test_cross_camera_person_tracking()
test_repeat_sighting_escalation_to_emergency()
test_ghost_detection_full_flow()
test_pipeline_handles_gemma_failure_gracefully()
test_pipeline_handles_empty_frame()
test_pipeline_respects_cooldown()
```

OUTPUT: Generate pipeline.py with CameraPipeline class, all dataclasses, orchestration logic, and test file. Use async/await throughout with asyncio.gather() for parallel calls.
```

---

## Quick Reference: V2 File Paths

| Sprint | File Path |
|--------|-----------|
| 2.1 | `connect/camera/rtsp_reader.py` |
| 2.1 | `connect/camera/frame_selector.py` |
| 2.1 | `connect/tests/test_camera.py` |
| 2.2 | `connect/camera/motion_detector.py` |
| 2.2 | `connect/tests/test_motion.py` |
| 2.3 | `connect/audio/audio_capture.py` |
| 2.3 | `connect/audio/yamnet_detector.py` |
| 2.3 | `connect/tests/test_audio.py` |
| 2.4 | `connect/transport/websocket_client.py` |
| 2.4 | `connect/transport/trigger_sender.py` |
| 2.4 | `connect/transport/sms_sender.py` |
| 2.4 | `connect/buffer/local_queue.py` |
| 2.4 | `connect/tests/test_transport.py` |
| 2.5 | `connect/main.py` |
| 2.5 | `connect/config.py` |
| 2.5 | `connect/ui/tray_app.py` |
| 3.1 | `backend/core/incident_tracker.py` |
| 3.1 | `backend/tests/unit/test_incident_tracker.py` |
| 3.2 | `backend/modes/indoor_mode.py` |
| 3.2 | `backend/modes/outdoor_mode.py` |
| 3.2 | `backend/modes/parking_mode.py` |
| 3.2 | `backend/modes/mixed_mode.py` |
| 3.2 | `backend/modes/shop_mode.py` |
| 3.2 | `backend/tests/unit/test_modes.py` |
| 3.3 | `backend/ai/reid_engine.py` |
| 3.3 | `backend/tests/unit/test_reid_engine.py` |
| 3.4 | `backend/core/cross_camera.py` |
| 3.4 | `backend/core/ghost_detector.py` |
| 3.4 | `backend/core/repeat_sighting.py` |
| 3.4 | `backend/tests/unit/test_cross_camera.py` |
| 3.5 | `backend/alerts/alert_router.py` |
| 3.5 | `backend/alerts/telegram_client.py` |
| 3.5 | `backend/alerts/voice_note.py` |
| 3.5 | `backend/alerts/sms_client.py` |
| 3.5 | `backend/tests/unit/test_alerts.py` |
| 3.6 | `backend/core/pipeline.py` |
| 3.6 | `backend/tests/unit/test_pipeline.py` |

---

*Vision OS V2 — DeepSeek Coding Prompts*

*Copy, paste, generate, test, commit. Repeat.*
