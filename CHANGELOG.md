# Changelog

## [Unreleased] — Phase 1–4 + Performance

### Phase 1 — Infrastructure foundation
- Replaced Google Memorystore with Upstash Redis (HTTP-based, no VPC needed)
- Structured Gemini JSON response contract across all 7 vision prompts
- NO_CHANGE short-circuit: Gemini returns `{"change_detected": false}` → skip DB write entirely
- Camera profile context injected into every Gemini decision call
- Global Gemini rate limiter (max 1 call per 8 seconds across all cameras)

### Phase 2 — AI pipeline upgrade
- Added YOLOv8 nano detection gate (ONNX Runtime). Filters frames with no relevant objects before Gemini. Reduces Gemini calls by ~40%.
- Added BoT-SORT multi-object tracker with Redis state. Persistent Track IDs per camera across Cloud Run restarts. IoU-based bbox matching (min 0.25).
- Added incident builder: decides if Gemini call is warranted based on track state changes (new track, 120s periodic update, track count change ±2)
- Created pipeline_v2.py: orchestrates full upgraded pipeline (YOLO → BoT-SORT → incident builder → CameraPipeline)
- Wired PipelineV2 into server.py and triggers.py. Falls back to V1 pipeline if YOLO unavailable.
- Frame quality gate before Gemini calls: brightness check (< 30), blur check (Laplacian var < 50), motion check (< 2% of frame)

### Phase 3 — Connection layer
- Added 5-method camera connection cascade: Dahua DHOpen P2P → Hikvision OpenAPI → Direct RTSP → RTMP push → WebSocket tunnel. Each method has 12s timeout. Logged like VPN connection flow.
- Added ONVIF auto-discovery (probes LAN subnet, tries default credentials, returns RTSP URIs)
- Added VPN-style connection UI in system tray app. Dark log area, color-coded status lines, CONNECT/DISCONNECT button, live cascade progress.
- Added Dahua/Hikvision credential fields to AppConfig

### Phase 4 — Performance
- Replaced ultralytics runtime with ONNX Runtime. yolov8n.onnx exported (12MB), inference ~200ms CPU. ultralytics removed from runtime dependencies.
- Added background drain thread to RTSPReader. Prevents stale frame accumulation on 25fps DVR streams.
- Parallelized dashboard DB queries with asyncio.gather(). 5 sequential DB calls → 1 gather (4x latency reduction). Eliminated duplicate get_camera_quota() DB call.

### UI/UX redesign
- Replaced dark navy/cyan theme with minimal off-white design
- Replaced emoji nav icons with Tabler icon font
- Added Central Intelligence summary section (purple card)
- Added Y-axis event timeline with left/right split: Left: analysis data (duration, frame coverage, confidence). Right: detection identity (person IDs, Re-ID tags). Purple: cross-camera correlation events.
- Timeline supports camera filter + time range selector

### Infrastructure
- Replaced Google Cloud SQL with Neon PostgreSQL (serverless, auto-scaling)
- Replaced google-generativeai SDK with google-cloud-aiplatform (Vertex AI)
- Removed MEGA.nz storage layer (PostgreSQL only)
- BoxMOT (FastReID) disabled due to numpy dependency conflict
- tensorflow excluded from PyInstaller build (~300MB saved)

### Documentation
- Complete rewrite of README.md, doc/ARCHITECTURE.md
- Rewrote backend/core/CONTEXT.md, backend/ai/CONTEXT.md, connect/CONTEXT.md
- Updated doc/LAUNCH_RUNBOOK.md with Redis health check, YOLO troubleshooting, removed Nagad/Stripe references