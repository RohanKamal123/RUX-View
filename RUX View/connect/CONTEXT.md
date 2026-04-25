# CONTEXT.md — Vision OS Connect (Client Agent)
# Module: connect/
# Sprint: 2.1–2.5
# Purpose: Lightweight client agent for customer premises

---

## What This Module Does

Lightweight background agent installed once per physical location.
Solves the NAT problem — all connections are outbound only.
Customer never touches router settings.

### Platform Priority
1. Windows (.exe via Nuitka) — primary
2. Android (.apk) — secondary

---

## File Structure

```
connect/
├── main.py                    Entry point
├── config.py                  Location + camera config
├── camera/
│   ├── rtsp_reader.py         RTSP stream connection
│   ├── frame_selector.py      Best frame from N frames
│   └── motion_detector.py     Pixel diff + zone masking
├── audio/
│   ├── yamnet_detector.py     YAMNet sound classification
│   └── audio_capture.py       Audio chunk extraction
├── transport/
│   ├── websocket_client.py    Persistent outbound connection
│   ├── trigger_sender.py      JPEG + audio POST to backend
│   └── sms_sender.py          SSL Wireless fallback
├── buffer/
│   └── local_queue.py         SQLite offline buffer
└── ui/
    └── tray_app.py            Windows system tray
```

---

## What It Does

1. Connect to IP camera on local network via RTSP
2. Run motion detection locally (pixel diff — free, no API)
3. Run sound detection locally (YAMNet — free, on device)
4. On trigger only:
   → Select best frame (8 frame lookahead, highest contour score)
   → Capture audio chunk (8 seconds around trigger)
   → POST JPEG + audio to backend via outbound HTTPS
5. Maintain persistent outbound WebSocket (heartbeat 30s)
6. Buffer locally if internet drops (SQLite, 48hr / 500 events max)
7. Flush buffer on reconnect (oldest first, backdated)
8. Send SMS via SSL Wireless for HIGH alerts during outage

## What It Does NOT Do
- No continuous video streaming to server
- No inbound connections (no port forwarding needed)
- No Gemma/AI on client (all AI is server-side)
- No video storage

## Key Decisions
- **D005** — Trigger-only (not continuous streaming)
- **D009** — Client agent solves NAT (outbound only)
- **D025** — Nuitka (NOT PyInstaller) for Windows .exe

## Dependencies
- opencv-python (motion detection)
- tensorflow (YAMNet audio)
- pyaudio (audio capture)
- websockets (persistent connection)
- httpx (trigger POST)
- sqlite3 (local buffer, stdlib)
- pystray (Windows system tray)
- nuitka (compile to .exe, dev only)
