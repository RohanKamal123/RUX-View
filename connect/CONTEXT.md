# CONTEXT.md — Vision OS Connect (Client Agent)
# Module: connect/
# Purpose: Windows desktop agent for on-premise camera capture + YOLO detection

---

## What This Module Does

Windows background agent (.exe) installed once per physical location.
Captures RTSP/P2P camera streams, runs on-device YOLO nano detection,
and sends relevant frames to the Cloud Run backend via outbound HTTPS.

Solves the NAT problem — all connections are outbound only.
Customer never touches router settings.

### Platform Priority
1. Windows (.exe via PyInstaller) — primary, most BD homes have a PC
2. Android (.apk) — secondary, for phone-as-relay use cases

---

## File Structure

```
connect/
├── main.py                    Entry point (VisionOSConnect class)
├── config.py                  AppConfig dataclass (JSON-based)
├── camera/
│   ├── connection_manager.py  5-method cascade (Dahua→Hikvision→RTSP→RTMP→WS)
│   ├── onvif_discovery.py     ONVIF LAN auto-discovery
│   ├── rtsp_discovery.py      RTSP port scanner
│   ├── rtsp_reader.py         RTSP stream reader (drain thread)
│   ├── rtsp_tester.py         RTSP connectivity tester
│   ├── frame_selector.py      Best frame from burst
│   └── motion_detector.py     MOG2 background subtraction
├── audio/
│   ├── yamnet_detector.py     YAMNet sound classification
│   └── audio_capture.py       Audio chunk extraction
├── transport/
│   ├── websocket_client.py    Persistent outbound connection
│   ├── trigger_sender.py      JPEG + audio POST to backend
│   └── sms_sender.py          SSL Wireless fallback
├── buffer/
│   └── local_queue.py         Offline queue (JSON file)
├── ui/
│   └── tray_app.py            Windows system tray (VPN-style UI)
├── models/
│   └── yolov8n.onnx           YOLOv8 nano model (12MB, ONNX format)
└── scripts/
    └── export_yolo_onnx.py    YOLO export script (dev only)
```

---

## Connection Cascade (connection_manager.py)

5 methods tried in priority order, each with 12s timeout.
Every attempt is logged in real time for the VPN-style connection UI.

| # | Method | Implementation | When It Works |
|---|--------|---------------|---------------|
| 1 | Dahua DHOpen P2P API | OpenAPI v1 token auth → relay RTSP URL | Dahua cameras with serial number (~85% BD market) |
| 2 | Hikvision OpenAPI | Hik-Connect cloud relay (stub — placeholder) | Hikvision cameras (~10% BD market) |
| 3 | Direct RTSP pull | cv2.VideoCapture with 5s timeout | LAN or public IP with port 554 open |
| 4 | RTMP push | Camera pushes to MediaMTX VPS; agent verifies pull URL | Cameras with RTMP support |
| 5 | WebSocket tunnel | Outbound tunnel via transport/websocket_client | Always works — agent-initiated |

### Connection Classes

```python
class ConnectionManager:
    """Manages camera connection with 5-method fallback cascade."""
    def __init__(self, credentials: CameraCredentials,
                 on_log=None, on_status=None): ...
    async def connect(self) -> ConnectionResult: ...
    async def disconnect(self) -> None: ...

class ConnectionMethod(Enum):
    DAHUA_P2P, HIKVISION, DIRECT_RTSP, RTMP_PUSH, WS_TUNNEL

class ConnectionStatus(Enum):
    DISCONNECTED, CONNECTING, CONNECTED, FAILED

class CameraCredentials:
    rtsp_url: str
    dahua_serial: str
    dahua_username: str
    dahua_password: str
    hik_serial: str
    hik_username: str
    hik_password: str
    rtmp_url: str
```

---

## On-Device AI

### YOLO Nano Detection Gate
- Model: YOLOv8 nano exported to ONNX format (yolov8n.onnx, 12MB)
- Runtime: ONNX Runtime (not ultralytics — faster, smaller dependency)
- Location: `connect/models/yolov8n.onnx`
- Inference: ~200ms on i5-8350U CPU
- Relevant classes: person, bicycle, car, motorcycle, bus, truck, cat, dog
- Confidence threshold: 0.35
- NMS IoU threshold: 0.45

### Export model
```bash
python -m connect.scripts.export_yolo_onnx
```
Requires `ultralytics` (dev only — not included in runtime dependencies).

---

## RTSPReader Drain Thread

Background thread in `rtsp_reader.py` continuously reads frames
from the camera stream and keeps only the latest frame.
Prevents stale frame accumulation on 25fps DVR streams.

---

## ONVIF Auto-Discovery (onvif_discovery.py)

Probes local network for ONVIF-compatible cameras.
- Probe ports: 80, 8080, 8000, 8899
- Timeout: 3.0s per probe
- Tries default credentials: Dahua (admin/admin123), Hikvision (admin/12345), generic
- Discovers all channel RTSP URIs

### Functions
```python
async def discover_cameras(subnet_prefix: str) -> list[CameraInfo]
    # Returns list of discovered cameras with RTSP URLs, brand, channels
```

---

## AppConfig Fields (config.py)

```python
@dataclass
class AppConfig:
    api_key: str = ""
    camera_id: str = ""
    camera_name: str = ""
    rtsp_url: str = ""
    mode: str = "indoor"
    backend_url: str = "https://api.visionos.app"
    audio_enabled: bool = True
    auto_start: bool = False
    ignore_zones: list | None = None
    # Dahua P2P credentials
    dahua_serial: str = ""
    dahua_username: str = ""
    dahua_password: str = ""
    # Hikvision credentials
    hik_serial: str = ""
    hik_username: str = ""
    hik_password: str = ""
    # RTMP push
    rtmp_url: str = ""
    # Motion parameters
    motion_threshold: float = 0.05
    motion_min_area: int = 8000
```

Config stored as JSON: `%APPDATA%/VisionOS/config.json`
Environment variable overrides: BACKEND_URL, RTSP_URL, CAMERA_ID, API_KEY, etc.

---

## Build

```bash
build_client.bat
```
Produces: `dist/VisionOS-Connect/`

Uses **PyInstaller** (NOT Nuitka). Key packaging decisions:
- `tensorflow` and `tensorflow_hub` explicitly excluded (`--exclude-module`)
- `pyaudio` included as hidden import
- `onnxruntime` included (YOLO inference)

## What It Does NOT Do
- No continuous video streaming to server
- No inbound connections (no port forwarding needed)
- No video storage
- TensorFlow excluded from build (~300MB saved vs including it)

---

## Key Decisions
- **D005** — Trigger-only (not continuous streaming)
- **D009** — Client agent solves NAT (outbound only)
- **D025** — PyInstaller (NOT Nuitka) for Windows .exe
- TensorFlow excluded — YOLO nano replaces YAMNet for on-device AI

## Dependencies
- opencv-python (motion detection, frame processing)
- onnxruntime (YOLO nano inference)
- pyaudio (audio capture)
- websockets (persistent connection)
- httpx (trigger POST)
- sqlite3 (local buffer, stdlib)
- pystray (Windows system tray)
- pyinstaller (compile to .exe, dev only)