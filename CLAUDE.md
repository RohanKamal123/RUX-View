# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Vision OS — AI-powered CCTV intelligence for the Bangladesh market. Cameras trigger
motion/audio events, a Cloud Run backend runs them through a Gemini vision pipeline,
and building owners get Telegram alerts. There is no continuous video streaming or
recording — see "Trigger-only architecture" below.

## Commands

### Backend dev server
```bash
uvicorn backend.dashboard.server:app --reload --port 8000
```
Serves the API at `/api/...`, the Jinja2 dashboard at `/`, and health at `/health`.

### Production run (what Docker/Cloud Run actually uses)
```bash
gunicorn backend.dashboard.server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

### Tests
```bash
pytest backend/tests/ -v                       # backend suite
pytest connect/tests/ -v                       # client agent suite
pytest backend/tests/unit/test_database.py -v  # one file
pytest backend/tests/unit/test_database.py::test_user_tier_query -v   # one test
pytest backend/tests/ --cov=backend --cov-report=term-missing         # coverage
```
`pytest.ini` sets `testpaths = backend/tests connect/tests`, `pythonpath = .`, and
`asyncio_mode = auto` (async tests need no `@pytest.mark.asyncio`). DB tests run against
in-memory SQLite (`aiosqlite`), not real Postgres, so pgvector-specific behavior is
skipped there — see `backend/tests/TESTING_GUIDE.md` for spinning up a real
`pgvector/pgvector` Postgres container for integration tests.

### Client agent (Windows desktop)
```bash
python -m connect.main       # run directly
build_client.bat             # PyInstaller build -> dist/VisionOS-Connect/
```

### Database migrations (Alembic)
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
python scripts/seed_database.py
```

### Deployment
```bash
bash infrastructure/deploy.sh --env production --tag v1.0.0
```
CI/CD is `.github/workflows/deploy.yml`: push to `main` runs `pytest backend/tests/` →
builds/pushes the Docker image to Artifact Registry → deploys to Cloud Run
(`us-central1`, service name `vision-os`) → smoke-tests `/health`.

There is no configured linter/formatter (no ruff/black/flake8/pyproject.toml) — don't
assume one exists.

## Architecture

Two independently deployed halves that only talk over HTTPS triggers:

- **`backend/`** — FastAPI app on Cloud Run. Receives triggers, runs the AI pipeline,
  serves the dashboard, stores everything in Postgres.
- **`connect/`** — Python agent that runs on a Windows PC at the customer site,
  reads RTSP/P2P camera streams, and POSTs trigger events to the backend. Packaged as
  a PyInstaller `.exe`.

There are also thin `ios/` (Swift) and `android/` (Kotlin) mobile app shells that
consume the backend API; most active development is backend + connect.

### Trigger-only, not streaming (D005)

The client never streams video to the server. It watches for motion (OpenCV MOG2) or
classified sound (YAMNet), and only then sends a JPEG frame (+ optional audio chunk) to
`backend/api/triggers.py`. This is the load-bearing architectural decision — assume it
when reasoning about cost, latency, or "real-time" claims.

### Backend request flow

```
connect agent --HTTPS trigger--> backend/api/triggers.py
                                       |
                                       v
                          PipelineManager (backend/core/pipeline_manager.py)
                          one CameraPipeline per camera_id, created lazily
                                       |
                                       v
                    PipelineV2 (backend/core/pipeline_v2.py) — production path
                    Stage 1: YOLO nano ONNX gate (backend/core/detection/yolo_detector.py)
                             filters frames with no person/vehicle/animal (~40% reduction)
                    Stage 2: BoT-SORT tracker (detection/botsort_tracker.py)
                             persistent track IDs per camera, state in Upstash Redis
                    Stage 3: Incident builder (detection/incident_builder.py)
                             decides whether a Gemini call is warranted this frame
                                       |
                                       v (if warranted)
                    CameraPipeline.process_trigger() (backend/core/pipeline.py)
                          1. IncidentTracker state machine: IDLE -> TRACKING -> CLOSE
                          2. Frame quality gate (brightness / blur / motion %, fail-open)
                          3. Gemini vision (backend/ai/ai_client.py, Vertex AI SDK)
                          4. Re-ID (backend/ai/reid_engine.py, pgvector cosine similarity)
                          5. Cross-camera correlation (backend/core/cross_camera.py)
                          6. Repeat-sighting escalation (backend/core/repeat_sighting.py)
                          7. Ghost detection (backend/core/ghost_detector.py)
                          8. On CLOSE_INCIDENT: Gemini incident decision -> alert routing
                             (backend/alerts/alert_router.py) -> persist event (backend/storage)
```

If YOLO/Redis are unavailable, PipelineV2 falls through directly to `CameraPipeline`
(V1 path) — that fallback is intentional, not a bug.

Per-camera pipelines are cached in `PipelineManager._pipelines` for the life of the
process; there's no eviction, so a long-lived server accumulates one `CameraPipeline`
per camera ever seen.

### Cost-control layers (matters when touching the pipeline)

Gemini calls are the dominant cost, so several independent throttles exist — don't
remove one without understanding the others:
- Global rate limit: 1 Gemini call / 8s across all cameras (`ai_client.py`).
- Incident builder: 1 call / 120s per camera (YOLO/tracker decides if a call is due).
- Per-incident throttle: 1 call / 15s inside `CameraPipeline._run_vision_analysis`.
- `NO_CHANGE` short-circuit: Gemini can return `{"change_detected": false}`, which
  skips Re-ID, cross-camera, alerting, and the DB write entirely.
- Frame quality gate: too dark / too blurry / too little motion vs. previous frame
  skips the Gemini call before it happens (fails open on decode errors).

### AI layer (`backend/ai/`)

`ai_client.py` is a single Vertex AI (`google-cloud-aiplatform`) client used for every
Gemini call — vision analysis, structured JSON analysis, incident decisions, NL query
answers, and daily/weekly digests. Auth is Application Default Credentials on Cloud
Run, not an API key (the `gemini_api_key` setting is legacy/unused post-migration to
Vertex AI). `analyse_frame_structured()` validates output against a controlled
vocabulary (event_type, threat_level, confidence) and discards results with
confidence < 0.6.

`reid_engine.py` does person re-identification via pgvector cosine similarity against
the `persons.embedding` column (>0.85 = confident match, 0.5–0.72 = ask Gemini as a
tiebreaker, <0.5 = mint a new `person_uid`). Note: BoxMOT/FastReID is commented out of
`requirements.txt` (numpy conflict) — embeddings currently come only from Gemini
appearance descriptions, not a dedicated embedding model.

### Alerting (`backend/alerts/`)

Routing is by threat level: `LOW` → dashboard only, `MEDIUM` → Telegram text,
`HIGH` → Telegram photo, `EMERGENCY` → Telegram + Kokoro-82M TTS voice note with
retries every 90s (max 3) before falling back to a secondary contact. SMS via SSL
Wireless is a fallback for `HIGH` alerts during internet outages only. Telegram
messages are plain text — no Markdown (timestamps contain underscores that Telegram
would otherwise interpret as formatting).

### Storage (`backend/storage/`)

Async SQLAlchemy 2.0 against Postgres (Neon in prod) with the `pgvector` extension.
Core tables: `events`, `persons` (has `embedding vector(512)`), `person_sightings`,
plus `scene_states`, `audio_events`, `shop_analytics`, `cameras`, `locations`, `users`.
All DB access is `async`/`await` — there is no sync session path. Retention is
tier-based (free 7 days, household 30, business 90; audio transcripts 1–3 days
regardless of tier) via `backend/storage/cleanup.py`.

### Dashboard (`backend/dashboard/`)

`server.py` is the FastAPI app entry point (`backend.dashboard.server:app`) and owns
the APScheduler jobs registered in its lifespan handler (daily digest 22:00, weekly
digest Monday 08:00, transcript cleanup daily 03:00 — `AsyncIOScheduler`, not the
`schedule` library). `auth.py` verifies Firebase ID tokens and exposes
`get_current_user()` / `require_tier()` dependencies used across `backend/api/`.
Subscription tiers gate features: `free` → `guard`/`household` → `guard_pro`/`business`.

### Client agent (`connect/`)

`main.py`'s `VisionOSConnect` is the orchestrator. Camera connectivity is a 5-method
fallback cascade tried in order (`connect/camera/connection_manager.py`): Dahua P2P →
Hikvision cloud relay (stub) → direct RTSP → RTMP push → outbound WebSocket tunnel —
this exists to avoid ever requiring the customer to configure port forwarding. A
background "drain thread" in `rtsp_reader.py` continuously reads the stream and keeps
only the latest frame, so triggers never fire against a stale frame from a buffered
DVR feed. On-device inference uses YOLOv8 nano exported to ONNX (`onnxruntime`, not
`ultralytics`, to keep the packaged `.exe` small) to pre-filter frames before they're
even sent to the backend. Offline triggers queue to a local SQLite file
(`connect/buffer/local_queue.py`) and flush when connectivity returns. Config persists
to `%APPDATA%/VisionOS/config.json`, overridable via env vars
(`BACKEND_URL`, `RTSP_URL`, `CAMERA_ID`, `API_KEY`, ...).

### Configuration

Both backend config (`backend/config.py`, Pydantic `Settings`, loads `.env`) and client
config (`connect/config.py`, JSON-backed `AppConfig`) are centralized — don't read
`os.environ` directly elsewhere. `.env.example` documents every backend variable
required.

## Documentation map

The repo has substantial existing docs — check them before re-deriving design context:
- `doc/ARCHITECTURE.md` — full technical architecture spec.
- `doc/DECISIONS-1.md` — numbered decision log (D001, D005, D022, ...). Treat as
  historical record, not always current: e.g. D025 says the Windows agent build uses
  Nuitka, but the codebase (`build_client.bat`, `connect/CONTEXT.md`) actually uses
  PyInstaller — the code and `CONTEXT.md` files win over stale decision entries.
  Referenced decision IDs above (D005, D026, D022, D023, D024) are current.
- `backend/*/CONTEXT.md` and `connect/CONTEXT.md` — per-module design notes, kept
  closer to the actual code than the top-level decision log.
- `doc/LAUNCH_RUNBOOK.md` — production launch checklist.
- `backend/tests/TESTING_GUIDE.md` — how the DB test suite works and how to run
  pgvector integration tests against a real Postgres instance.
- `CODEBASE.md` / `PROJECT_STRUCTURE.md` — earlier full-repo structure dumps; this
  file supersedes them for architecture/workflow purposes, but they're useful as a
  file-by-file index if you need to locate something not covered here.
