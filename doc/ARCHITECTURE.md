# ARCHITECTURE.md
# Vision OS — Complete Technical Specification
# Version 2.0 | Locked for V2 Build

---

## 1. PRODUCT OVERVIEW

### What It Is
Vision OS is an AI-powered CCTV intelligence SaaS platform for the Bangladesh market.
It connects to existing IP cameras and adds an intelligence layer — real-time incident
detection, cross-camera person tracking, and natural language querying over security events.

### What It Is Not
- Not a recording product (customers keep their own DVR)
- Not a camera hardware product
- Not a replacement for Hikvision/Dahua
- Not a cloud storage product

### One Line Pitch
"Plug into any camera. Get AI-powered alerts and natural language search over your security — starting at 299 BDT/month."

### Target Market
- Primary: Homeowners and residences in Bangladesh
- Secondary: Shop owners, godown operators, small offices
- Geography: Bangladesh only (V1)
- Camera range: 1–5 cameras per user (V1)

---

## 2. SYSTEM ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────┐
│              CUSTOMER PREMISES (per location)               │
│                                                             │
│  IP Camera(s) ──RTSP/P2P──► Vision OS Connect (Windows .exe)│
│                               ├── YOLO nano gate (ONNX)     │
│                               ├── BoT-SORT tracker (Redis)  │
│                               ├── 5-method connection       │
│                               │   cascade (P2P→RTSP→tunnel)│
│                               ├── Best frame capture        │
│                               └── Outbound HTTPS only       │
└──────────────────────────────┬──────────────────────────────┘
                               │ JPEG triggers (outbound only)
                               │ no NAT issues
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              YOUR BACKEND (Google Cloud Run)                │
│                                                             │
│  FastAPI ──► Trigger receiver (session dedup 45s)          │
│              ├── Pipeline V2 orchestrator                   │
│              │   ├── YOLO gate (cloud-side verify)          │
│              │   ├── BoT-SORT tracker (Redis state)         │
│              │   ├── Incident builder (Gemini gate)         │
│              │   └── CameraPipeline (V1 fallback)           │
│              ├── Incident state machine (per camera)        │
│              ├── Cross-camera correlation engine            │
│              ├── Re-ID engine (pgvector cosine similarity)  │
│              ├── AI client (Vertex AI Gemini 2.x Flash)     │
│              ├── Query engine (NL → SQL → Gemini 2.x)      │
│              ├── Analytics engine (shop/business mode)      │
│              ├── Alert router (Telegram + SMS)             │
│              └── Dashboard server                           │
└──────┬────────────────────┬───────────────────────────────┘
       │                    │
       ▼                    ▼
┌─────────────┐    ┌────────────────────────┐
│ GEMINI API  │    │ NEON POSTGRES          │
│ (Vertex AI) │    │ + pgvector             │
│             │    │                        │
│ Gemini 2.x  │    │ events                 │
│ Flash       │    │ persons                │
│ → vision    │    │   + embedding vector   │
│ → decisions │    │ scene_states           │
│ → chatbot   │    │ analytics              │
│ → queries   │    │ cameras                │
│ → digests   │    │ users                  │
│             │    │ locations              │
└─────────────┘    └────────────────────────┘
       │                          │
       ▼                          ▼
┌─────────────────────┐  ┌───────────────────┐
│ UPSTASH REDIS       │  │ USER INTERFACES   │
│                     │  │                   │
│ Track:{camera_id}   │  │ Web Dashboard     │
│ (TTL 300s)          │  │ Android Viewer App│
│ Session state       │  │ Telegram Bot      │
│ Re-ID cache         │  └───────────────────┘
└─────────────────────┘
```

---

## 3. VISION OS CONNECT (CLIENT AGENT)

### Purpose
Lightweight background agent installed once per physical location.
Solves the NAT problem — all connections are outbound only.
Customer never touches router settings.

### Platform Priority
1. Windows (.exe via PyInstaller) — primary, most BD homes have a PC
2. Android (.apk) — secondary, for phone-as-relay use cases

### 5-Method Camera Connection Cascade

The connect agent tries 5 connection methods in priority order,
each with a 12-second timeout. Every attempt is logged like a VPN connection flow.

| Priority | Method | When It Works | Coverage |
|----------|--------|---------------|----------|
| 1 | Dahua DHOpen P2P API | Dahua cameras with serial number | ~85% of BD market |
| 2 | Hikvision OpenAPI | Hikvision Hik-Connect cloud relay | ~10% of BD market |
| 3 | Direct RTSP pull | LAN or public IP with port 554 | Always if reachable |
| 4 | RTMP push | Camera supports RTMP outbound | Some Hikvision models |
| 5 | WebSocket tunnel | Always — agent-initiated outbound | 100% guaranteed |

### What It Does
```
1. Connect to IP camera via cascade (P2P → RTSP → tunnel)
2. Run YOLO nano detection gate (ONNX Runtime, on-device)
   → Filters frames with no relevant objects (person/vehicle/animal)
   → Reduces Gemini calls by ~40%
3. Run BoT-SORT tracker (Redis state, IoU matching)
   → Assigns persistent Track IDs per camera
   → State stored in Upstash Redis: key="track:{camera_id}", TTL=300s
4. Run incident builder (decides if Gemini call is warranted)
   Rules:
   → New track appeared → CALL Gemini
   → No Gemini call in 120s → CALL Gemini (periodic update)
   → Track count changed ±2 → CALL Gemini
   → Otherwise → SKIP Gemini
5. On Gemini-approved trigger only:
   → Select best frame (highest confidence detection)
   → POST JPEG to backend via outbound HTTPS
6. Maintain persistent WebSocket (heartbeat 30s)
7. Buffer locally if internet drops (JSON file, 48hr / 500 events max)
8. Flush buffer on reconnect (oldest first, backdated)
9. Send SMS via SSL Wireless for HIGH alerts during outage
```

### What It Does NOT Do
```
→ No continuous video streaming to server
→ No inbound connections (no port forwarding needed)
→ No video storage
→ No TensorFlow (excluded from PyInstaller build — ~300MB saved)
```

### Install Flow for Customer
```
1. Sign up at dashboard
2. Dashboard generates API key
3. Download Vision OS Connect
4. Open app → enter API key
5. Camera auto-discovery (ONVIF) or manual RTSP URL entry
6. Name the camera: "Front Gate"
7. Name the location: "Home - Mirpur"
8. Select camera mode: Indoor/Outdoor/Parking/Mixed/Shop
9. Draw ignore zones on preview (optional)
10. Click Connect → cascade tries all methods → green status
11. First trigger fires within minutes
```

### Client File Structure
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
│   ├── yamnet_detector.py     YAMNet sound classification (stub/disabled)
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

### Offline Behaviour
```
STATE 1: Full internet ✅
→ Normal operation

STATE 2: Internet down, local network up
→ Detection continues locally
→ Triggers queue in local JSON buffer
→ HIGH threat → SSL Wireless SMS sent (~0.30 BDT)
→ Internet returns → flush queue → backdated alerts
→ Telegram digest: "While offline, 3 events occurred"

STATE 3: Full outage (power/router dead)
→ Nothing works → accept for V1
→ Camera itself may have local SD storage (not our concern)
```

---

## 4. DETECTION PIPELINE (3-STAGE GATE)

### Stage 1: YOLO Nano Gate
- Model: YOLOv8 nano exported to ONNX format (yolov8n.onnx, 12MB)
- Runtime: ONNX Runtime (not ultralytics — faster, smaller dependency)
- Input: 640×640 JPEG frame, normalized RGB
- Output: DetectionResult with bboxes, class names, confidence
- Relevant classes: person (0), bicycle (1), car (2), motorcycle (3), bus (5), truck (7), cat (15), dog (16)
- Confidence threshold: 0.35
- NMS IoU threshold: 0.45
- Inference speed: ~200ms on i5-8350U CPU
- Effect: filters ~40% of frames before Gemini is called

### Stage 2: BoT-SORT Tracker
- Stateful multi-object tracker with Redis persistence
- Track state per camera stored as Redis hash:
  ```
  key: "track:{camera_id}"
  TTL: 300 seconds (5 minutes — matches session timeout)
  ```
- Track matching: IoU-based (minimum threshold 0.25)
- Track ID format: {cam_prefix}_{sequential}, e.g. "FRONT_001"
- Returns: TrackingResult with tracks, new_tracks, lost_tracks, track_summary

### Stage 3: Incident Builder
Decides if Gemini vision call is warranted based on track state changes.

| Rule | Action |
|------|--------|
| New track appeared | CALL Gemini |
| No Gemini call in 120s (periodic update) | CALL Gemini |
| Track count changed ±2 | CALL Gemini |
| Same tracks, called Gemini recently | SKIP |
| Gemini returned change_detected=False | SKIP (extends skip window) |

NO_CHANGE short-circuit: Gemini returns {"change_detected": false} → skips DB write entirely.

### Frame Quality Gate (V1 Pipeline)
Before any Gemini call, the V1 pipeline runs three quality checks:
1. Mean brightness < 30 → too dark, skip
2. Laplacian variance < 50 → too blurry, skip
3. Motion area < 2% of frame → too little motion, skip

---

## 5. INTELLIGENCE PIPELINE

### Pipeline V2 (Production — default)
```
JPEG frame
  → YOLO gate (filter irrelevant frames)
  → BoT-SORT tracker (assign Track IDs, Redis state)
  → Incident builder (decide if Gemini needed)
  → CameraPipeline.process_trigger()
      → Frame quality gate (brightness/blur/motion checks)
      → Gemini 2.x vision analysis (structured JSON)
      → Re-ID engine (pgvector cosine similarity)
      → Cross-camera correlation
      → Repeat sighting escalation
      → Ghost detection
      → Gemini incident decision
      → Alert routing (Telegram/SMS)
      → Database save
```

### Pipeline V1 (Fallback — used when YOLO unavailable)
```
Trigger
  → Incident tracker state machine
  → Frame quality gate
  → Gemini vision analysis
  → Re-ID → Cross-camera → Repeat sighting → Ghost detection
  → Gemini incident decision
  → Alert routing → DB save
```

### 6.1 Incident State Machine

Every camera has its own independent state machine.

```
┌─────────────┐
│    IDLE     │◄────────────────────────────────┐
│             │                                 │
│ Gemini: OFF │                                 │
│ Cost: $0    │                                 │
│             │                                 │
│ motion pass │                                 │
│ filters     │                                 │
└──────┬──────┘                                 │
       │                                        │
       │ motion + cooldown elapsed              │
       ▼                                        │
┌─────────────┐                                 │
│  TRACKING   │                                 │
│             │                                 │
│ Gemini: ON  │                                 │
│ burst when  │                                 │
│ behaviour   │                                 │
│ changes     │                                 │
└──────┬──────┘                                 │
       │                                        │
       │ no motion 3–6s OR max cap hit          │
       ▼                                        │
┌─────────────┐                                 │
│    CLOSE    │─────────────────────────────────┘
│  INCIDENT   │
│             │
│ send full   │
│ timeline    │
│ to Gemini   │
│             │
│ route alert │
│ save to DB  │
└─────────────┘
```

### 6.2 Threat Levels

Six threat levels used throughout the pipeline:

| Level | Order | Description | Alert Action |
|-------|-------|-------------|--------------|
| PENDING | -1 | Initial placeholder before analysis | None |
| LOW | 0 | Routine activity | Dashboard only |
| MEDIUM | 1 | Suspicious but not urgent | Telegram text |
| HIGH | 2 | Active threat | Telegram photo + caption |
| CRITICAL | 3 | High-priority threat | Telegram urgent message |
| EMERGENCY | 4 | Immediate danger | Emergency voice note + SMS |

### 6.3 AI Call Gate (When to Call, When to Skip)

```
ALWAYS CALL GEMINI (via incident builder):
→ New track appeared (new person/vehicle)
→ 120s periodic update timer fires
→ Track count changed significantly (±2)

ALWAYS CALL GEMINI (legacy V1 pipeline):
→ First frame of any incident
→ Pixel diff crosses URGENT threshold
→ Loitering escalation timer fires
→ After hours ANY motion (night mode)
→ Re-ID uncertainty (similarity 0.5–0.72)
→ Audio trigger + no current visual incident open

SKIP GEMINI:
→ Same tracks, called Gemini within 120s
→ Gemini returned change_detected=False
→ YOLO gate found no relevant objects
→ Frame quality checks failed (dark/blurry/still)
→ Within burst cooldown AND pixel diff unchanged
```

### 6.4 Rate Limiting

Three layers of rate limiting:

| Layer | Limit | Scope | Purpose |
|-------|-------|-------|---------|
| Global | 1 call per 8s | All cameras combined | API cost control |
| Per-camera (V1) | 1 call per 15s | Single camera | Prevent redundant analysis |
| Per-camera (incident builder) | 1 call per 120s | Single camera | Periodic update interval |
| Frame quality gate | N/A | Per frame | Skip dark/blurry/still frames |

---

## 6. AI STACK

### Stack Layers

| Layer | Technology | SDK | Purpose |
|-------|-----------|-----|---------|
| AI Vision | Vertex AI Gemini 2.x Flash | google-cloud-aiplatform 1.71.0 | Frame analysis, threat detection |
| Audio analysis | Vertex AI Gemini 2.x Flash | google-cloud-aiplatform 1.71.0 | Transcription + threat detection (same model) |
| Re-ID | pgvector cosine similarity | pgvector 0.2.4 | Person identity matching |
| Re-ID tiebreaker | Vertex AI Gemini 2.x Flash | google-cloud-aiplatform 1.71.0 | Uncertainty zone (0.5–0.72) |

NOT used: google-generativeai SDK, OpenAI Whisper, Groq API, BoxMOT (disabled).

### Gemini 2.x Flash — Unified Client (backend/ai/ai_client.py)

All AI functions go through a single client using `google-cloud-aiplatform` SDK (Vertex AI).
Model: `gemini-2.5-flash` (may be updated to newer 2.x version).

### Prompt Types (7 total)

1. **analyse_frame()** — Fast vision analysis for live incidents
2. **analyse_frame_structured()** — Controlled-vocabulary structured JSON (validates schema, retries once on failure)
3. **analyse_frame_with_second_pass()** — Two-layer: vision → text summary → security verdict
4. **analyse_frame_detailed()** — Exhaustive clothing/accessories for NL queries
5. **analyse_shop_entry()** — Demographics for shop analytics
6. **analyse_audio()** — Audio transcription + threat detection (same Gemini model)
7. **make_incident_decision()** — Security verdict from incident timeline

### Structured Response Contract

All vision functions return a standardised JSON format:

```json
{
  "change_detected": true,
  "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "description": "one sentence, what is happening",
  "action": "recommended action for building owner",
  "objects_detected": ["person", "vehicle"]
}
```

NO_CHANGE short-circuit: `{"change_detected": false}` — skips DB write entirely.

### NO_CHANGE Short-Circuit
All Gemini prompts include a NO_CHANGE fallback instruction. If Gemini determines
the scene is unchanged, it returns `{"change_detected": false}`. The pipeline then:
1. Records the NO_CHANGE timestamp (extends skip window in incident builder)
2. Skips all downstream processing (Re-ID, cross-camera, alerts, DB write)
3. Returns PipelineResult with change_detected=False

This reduces Gemini costs by ~30% on top of the 40% reduction from YOLO gate.

### Structured Analysis Schema Validation
analyse_frame_structured() validates every Gemini response against a controlled vocabulary:
- event_type: person_entering|person_leaving|loitering|vehicle|crowd|fight|unknown
- threat_level: LOW|MEDIUM|HIGH|EMERGENCY|CRITICAL
- confidence: 0.0–1.0 (discarded if < 0.6)
- If validation fails → retries once → falls back to safe default

---

## 7. RE-ID ENGINE

### Approach: pgvector Cosine Similarity

```
Step 1: Gemini extracts person appearance description from frame
Step 2: Re-ID engine calls identify() with:
  - Frame crop
  - Location ID
  - User ID
Step 3: pgvector cosine similarity in Postgres
  SELECT person_uid FROM persons
  ORDER BY embedding <-> %s LIMIT 5
  > 0.85  → confident match → return existing ID
  0.5–0.72 → uncertain → go to Step 4 (Gemini tiebreaker)
  < 0.5   → new person → mint new ID
Step 4 (uncertain zone only):
  Gemini appearance description comparison via reid_tiebreaker()
```

Note: BoxMOT (FastReID backend) is disabled due to numpy dependency conflict.
The embedding column (vector(512)) exists in the schema but is populated differently
or left empty until a suitable embedding model is integrated.

### Person Signature Format
```
"male 20s red-shirt black-jeans white-sneakers backpack"
```

### Familiar Face Labelling
Owner can label any Re-ID profile: "Postman", "Gardener", "Staff 1", "Family"
Known persons generate different alert formats:
  "Known visitor [Postman] at front gate"
  vs
  "Unknown person at front gate"

---

## 8. STORAGE

### Layer 1: Neon PostgreSQL (Primary)
- Serverless Postgres with pgvector extension
- Fully managed, auto-scaling
- Used for all structured data: events, cameras, users, persons, analytics

### Layer 2: Upstash Redis (Cache + State)
- HTTP-based Redis (no VPC needed, works with Cloud Run)
- Used for:
  - BoT-SORT tracker state (key: "track:{camera_id}", TTL: 300s)
  - Session deduplication state
  - Re-ID cache
  - Rate limiting counters

### Removed
- MEGA.nz (Layer 1 — removed entirely)
- Google Cloud SQL (replaced by Neon)

### Database Schema Highlights

**events** — Core incident table
```sql
CREATE TABLE events (
  id                  SERIAL PRIMARY KEY,
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  camera_id           VARCHAR(100) NOT NULL,
  incident_id         VARCHAR(100) NOT NULL,
  timestamp_start     TIMESTAMPTZ NOT NULL,
  timestamp_end       TIMESTAMPTZ,
  duration_sec        FLOAT,
  threat_level        VARCHAR(10),        -- PENDING/LOW/MEDIUM/HIGH/CRITICAL/EMERGENCY
  alert_sent          BOOLEAN DEFAULT FALSE,
  alert_type          VARCHAR(30),
  camera_mode         VARCHAR(20),
  gemini_decision     JSONB,
  timeline_json       JSONB,
  thumbnail_url       TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

**persons** — Re-ID person profiles
```sql
CREATE TABLE persons (
  id                  SERIAL PRIMARY KEY,
  person_uid          VARCHAR(20) NOT NULL,
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  sighting_count      INTEGER DEFAULT 0,
  threat_flags        INTEGER DEFAULT 0,
  is_staff            BOOLEAN DEFAULT FALSE,
  user_label          VARCHAR(100),
  appearance_history  JSONB,
  embedding           vector(512),        -- pgvector (currently unused)
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(person_uid, user_id)
);

CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops);
```

---

## 9. ALERT SYSTEM

### Alert Routing by Threat Level

```
LOW:        → Dashboard only, no Telegram
MEDIUM:     → Telegram text message
HIGH:       → Telegram photo + caption
CRITICAL:   → Telegram urgent message + voice note
EMERGENCY:  → Emergency voice note + SMS fallback

During internet outage (HIGH only):
            → SSL Wireless SMS (~0.30 BDT)
            "VisionOS ALERT: High threat at [camera].
             Check Telegram when online."
```

### Emergency Voice Note
Generated on backend via Kokoro-82M TTS (ONNX runtime, Apache 2.0).
"Vision OS emergency alert. High threat detected at [camera name]."
Converted WAV → OGG Opus via ffmpeg for Telegram.
Sent as .ogg file — plays automatically on notification.

### 10. SESSION-BASED EVENT DEDUPLICATION

Frames arriving within 45 seconds of the last motion are merged into the same event.

```
Session state (per camera, in-memory dict):
{
  "event_id": str,
  "started_at": datetime,
  "last_motion_at": datetime,
  "frame_count": int,
  "max_threat": str (PENDING/LOW/MEDIUM/HIGH/CRITICAL/EMERGENCY)
}

Background cleanup loop runs every 15s.
Closes sessions where last_motion_at > 45s ago.
Updates event with final duration and max_threat.
```

---

## 11. COST ESTIMATES

### Per Camera Per Day

```
Gemini 2.x Flash — structured analysis
  9 incidents × 1 frame each (YOLO gate filtered ~40%)
  + 9 decision calls (~800 tokens each)
  Gemini 2.x Flash pricing: ~$0.00010/image, ~$0.00004/decision
  = ~$0.005/day  (40% reduction from YOLO gate)

Google Cloud Run + Neon + Upstash Redis
  Shared, amortised per camera
  = ~$0.007/day

Firebase Auth
  Free tier covers V1 scale
  = $0.000/day
─────────────────────────────
HOUSEHOLD: ~$0.012/day = ~$0.36/month
BUSINESS:  ~$0.018/day = ~$0.54/month
FREE:      ~$0.004/day = ~$0.12/month
```

---

## 12. DEPENDENCIES

```
BACKEND (Python 3.11)
────────────────────────────────
fastapi, uvicorn, gunicorn     Web framework
google-cloud-aiplatform        Vertex AI Gemini SDK
psycopg2-binary, asyncpg       Postgres + async driver
sqlalchemy                     ORM
pgvector                       Vector similarity
opencv-python                  Frame processing
firebase-admin                 Firebase Auth
httpx                          Async HTTP
apscheduler                    Cron scheduler
kokoro-onnx                    TTS for voice notes
upstash-redis                  Redis client
Pillow                         Image processing
onnxruntime                    YOLO inference
pydantic-settings              Config management

CLIENT AGENT (Python → .exe via PyInstaller)
────────────────────────────────
opencv-python                  Motion detection
onnxruntime                    YOLO nano inference
pyaudio                        Audio capture
websockets                     Persistent connection
httpx                          Trigger POST (async)
sqlite3                        Local buffer (stdlib)
pystray                        Windows system tray
pyinstaller                    Compile to .exe (dev only)

INFRASTRUCTURE
────────────────────────────────
Google Cloud Run               Backend hosting
Neon PostgreSQL                Database + pgvector
Upstash Redis                  Cache + tracker state
Vertex AI Gemini               Vision + reasoning
Firebase Auth                  User authentication
SSL Wireless BD                SMS fallback
bKash Payment Gateway          Billing
Telegram Bot API               Alerts (free)
```

---

## 13. FILE STRUCTURE

```
vision-os/
│
├── connect/                         CLIENT AGENT (.exe)
│   ├── main.py                      entry point
│   ├── config.py                    AppConfig dataclass
│   ├── camera/
│   │   ├── connection_manager.py    5-method cascade
│   │   ├── onvif_discovery.py       LAN auto-discovery
│   │   ├── rtsp_discovery.py        RTSP port scanner
│   │   ├── rtsp_reader.py           stream reader + drain
│   │   ├── rtsp_tester.py           RTSP connectivity test
│   │   ├── frame_selector.py        best frame from N frames
│   │   └── motion_detector.py       MOG2 background subtraction
│   ├── audio/
│   │   ├── yamnet_detector.py       YAMNet classification
│   │   └── audio_capture.py         audio chunk extraction
│   ├── transport/
│   │   ├── websocket_client.py      persistent outbound WS
│   │   ├── trigger_sender.py        HTTP POST to backend
│   │   └── sms_sender.py            SSL Wireless fallback
│   ├── buffer/
│   │   └── local_queue.py           JSON offline buffer
│   ├── ui/
│   │   └── tray_app.py              Windows system tray
│   ├── models/
│   │   └── yolov8n.onnx             YOLO nano model
│   ├── scripts/
│   │   └── export_yolo_onnx.py      model export (dev)
│   └── tests/
│       ├── test_motion.py
│       ├── test_client_mega.py
│       ├── test_audio.py
│       ├── test_transport.py
│       ├── test_local_queue.py
│       ├── test_camera.py
│       ├── test_integration.py
│       ├── test_main_orchestrator.py
│       └── test_build_verify.py
│
├── backend/                         SERVER (Cloud Run)
│   ├── api/
│   │   ├── triggers.py              receive triggers + session dedup
│   │   ├── cameras.py               camera management
│   │   ├── queries.py               NL query endpoints
│   │   ├── payments.py              bKash payment API
│   │   ├── analytics.py             analytics API
│   │   ├── users.py                 user management
│   │   ├── locations.py             location management
│   │   ├── admin_cameras.py         admin camera control
│   │   ├── public_signup.py         public registration
│   │   ├── clips.py                 event clip retrieval
│   │   └── telegram_test.py         Telegram test endpoint
│   │
│   ├── core/
│   │   ├── pipeline.py              CameraPipeline orchestrator
│   │   ├── pipeline_v2.py           upgraded pipeline with YOLO gate
│   │   ├── pipeline_manager.py      per-camera pipeline factory
│   │   ├── incident_tracker.py      IDLE/TRACKING/CLOSE state machine
│   │   ├── cross_camera.py          multi-camera correlation
│   │   ├── ghost_detector.py        unaccounted person logic
│   │   ├── repeat_sighting.py       frequency escalation
│   │   └── detection/
│   │       ├── yolo_detector.py     YOLO nano ONNX gate
│   │       ├── botsort_tracker.py   BoT-SORT + Redis tracker
│   │       └── incident_builder.py  Gemini call gating
│   │
│   ├── ai/
│   │   ├── ai_client.py             Vertex AI Gemini unified client
│   │   ├── reid_engine.py           pgvector Re-ID
│   │   └── query_engine.py          NL query processing
│   │
│   ├── analytics/
│   │   ├── shop_analytics.py        customer counting + demographics
│   │   ├── digest_generator.py      daily + weekly digest
│   │   ├── report_builder.py        business reports
│   │   ├── advanced_analytics.py    advanced analytics
│   │   ├── anomaly_detector.py      anomaly detection
│   │   ├── camera_metrics.py        camera performance metrics
│   │   ├── trend_analyzer.py        trend analysis
│   │   └── usage_tracker.py         usage tracking
│   │
│   ├── alerts/
│   │   ├── alert_router.py          route by threat level
│   │   ├── telegram_client.py       Telegram Bot API
│   │   ├── voice_note.py            Kokoro-82M TTS
│   │   └── sms_client.py           SSL Wireless integration
│   │
│   ├── storage/
│   │   ├── hybrid_crud.py           unified CRUD (PG only)
│   │   ├── pg_crud.py               Postgres CRUD operations
│   │   ├── crud.py                  legacy CRUD interface
│   │   ├── database.py              SQLAlchemy models
│   │   └── engine.py                async DB engine
│   │
│   ├── dashboard/
│   │   ├── server.py                FastAPI app + lifespan
│   │   ├── auth.py                  Firebase Auth middleware
│   │   ├── routes.py                dashboard page routes
│   │   ├── templates/               Jinja2 templates
│   │   └── static/                  CSS + JS
│   │
│   ├── i18n/                        Internationalization
│   │
│   └── tests/
│       ├── unit/
│       └── fixtures/
│
├── doc/
│   ├── ARCHITECTURE.md              this document
│   ├── LAUNCH_RUNBOOK.md            deployment runbook
│   ├── E2E_TESTING_GUIDE.md         end-to-end test guide
│   ├── MANUAL_SETUP_STEPS.md        manual setup
│   ├── INDEX.md                     documentation index
│   └── internal/                    working docs
│
├── infrastructure/
│   ├── cloud_run_config.yaml        Cloud Run YAML config
│   └── deploy.sh                    deployment script
│
├── alembic/                         DB migration versions
├── masscan/                         RTSP camera discovery
├── android/                         Android viewer app (Kotlin)
├── ios/                             iOS viewer app (Swift)
└── scripts/                         utility scripts
```

---

*ARCHITECTURE.md — Vision OS V2*
*Status: Rewritten — corrected stack, added detection pipeline V2, connection cascade*
*Last updated: 2026-06-18*