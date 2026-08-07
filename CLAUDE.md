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
                    Session tracking (in triggers.py, per camera_id)
                    Frames within SESSION_TIMEOUT_SEC (default 180s) of the last
                    motion merge into the active event; otherwise a new event is
                    created. A background loop (_session_cleanup_loop) closes
                    sessions every 15s once they go quiet, writing timestamp_end /
                    duration_sec / max_threat (threat escalates via _THREAT_ORDER,
                    PENDING < LOW < MEDIUM < HIGH < CRITICAL < EMERGENCY).
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

`PipelineV2.process_frame()` takes a `dry_run: bool` flag — when `True`, Gemini calls
still happen for real (so it's still billable) but DB writes, Redis writes, and alert
sends are all suppressed. This is what the clip-analysis/tuning tools below use to test
against production logic without touching production state.

### Cost-control layers (matters when touching the pipeline)

Gemini calls are the dominant cost, so several independent throttles exist — don't
remove one without understanding the others. All of them are now runtime-tunable, not
just hardcoded (see "Runtime-tunable thresholds" below) — the values here are defaults:
- Global rate limit: 1 Gemini call / 8s across all cameras (`ai_client.py`,
  `gemini_min_interval_sec`).
- Incident builder: 1 call / 60s per camera (`incident_builder.py`,
  `gemini_interval_sec`) — the module docstring says 120s, that's stale; 60s is what's
  enforced (see `doc/NUMERICAL_AUDIT.md` Critical Finding #1).
- Per-incident throttle: 1 call / 15s inside `CameraPipeline._run_vision_analysis`
  (`per_incident_throttle_sec`). Note: `pipeline.py`'s `_VISION_THROTTLE_SECONDS`
  instance attribute is dead code (never assigned to `self`) — the 15s value is a
  separate hardcoded literal at the actual check site (Critical Finding #2).
- `NO_CHANGE` short-circuit: Gemini can return `{"change_detected": false}`, which
  skips Re-ID, cross-camera, alerting, and the DB write entirely.
- Frame quality gate: too dark / too blurry / too little motion vs. previous frame
  skips the Gemini call before it happens (fails open on decode errors).

### Runtime-tunable thresholds (`backend/core/config_store.py`)

Every numeric constant enumerated in `doc/NUMERICAL_AUDIT.md` (58 keys — detection,
motion, frame-quality gates, tracking, Gemini gating, Re-ID, ghost/repeat, alerts,
storage, retention, RTSP, clip analysis) has a hardcoded default in
`config_store.DEFAULTS` and can be overridden live by writing a JSON blob to the
Upstash Redis key `visionos:tunable_config` — no redeploy needed. `get_config()`
merges stored overrides over defaults and returns `{values, defaults, modified_keys,
category_groups, live_effective}`; `set_config()`/`reset_config()` mutate it. Exposed
via `backend/api/config.py` as `GET/POST /api/config/thresholds` and
`POST /api/config/thresholds/reset`, and edited from the dashboard's Tuning page
(`backend/dashboard/templates/tuning.html`, route `/dashboard/tuning`).
`LIVE_EFFECTIVE` is the subset of keys that affect a single frame's detection outcome
(excludes alerts/storage/caching/retention/account-quota categories) — that's the set
the clip-test tool below treats as "affects this run".

If you change a threshold's *default*, update `config_store.DEFAULTS` — don't just
edit the call site — otherwise the tuning UI and `doc/NUMERICAL_AUDIT.md` drift out of
sync with the code again.

**Don't assume a key in `DEFAULTS` is actually read anywhere without checking** — a
systematic audit originally found ~21 of the 59 keys declared but never consumed
outside `config_store.py` itself (moving their tuning-dashboard slider did nothing).
All of them are now wired: `retention_*_days` / `transcript_retention_days` /
`max_cameras_per_user` (Dashboard/Storage sections), `alert_retry_interval_sec` /
`alert_max_retries` (`alert_router.py`) / `telegram_timeout_sec` (`telegram_client.py`),
the four `cache_ttl_*` keys (`cdn_manager.py`), `db_pool_*` (see below), and
`rtsp_*`/`motion_*` (see "Client config sync" below). Two keys were checked and found
to have no live target worth wiring rather than being fixed: `pg_find_similar_limit`
targets `PostgresCRUD.find_similar_persons()`, an orphaned duplicate of the function
`reid_engine.py` actually calls (`crud.find_similar_persons()`); `gemini_digest_word_limit`
targets a digest code path superseded by `DigestGenerator`'s template-formatted output
(no Gemini call at all — see Dashboard section). Verify with
`grep -rn "<key_name>" backend/ connect/` before trusting that a key does anything —
this list can drift again.

**`db_pool_*` live reconfiguration (`backend/storage/engine.py`).** The engine used to
be a bare module-level global built once at import time — changing `db_pool_size` /
`db_max_overflow` / `db_pool_timeout_sec` / `db_connect_timeout_sec` needed a redeploy.
`refresh_engine_config()` now compares config_store's live values against
`_current_pool_config` (the pool the active engine was built with) and, if they
differ, builds a replacement engine + session factory under `_engine_lock` and disposes
the old one — `create_session()` always reads the current module globals, so callers
need no changes. Three call sites trigger it: once on server startup (picks up
whatever was already in Redis before this process started), immediately after every
`POST /api/config/thresholds` write (`backend/api/config.py`, so the instance that
handled the write sees it right away), and every 5 minutes from the APScheduler job
`db_pool_config_refresh` (`backend/dashboard/server.py`, the fallback for other Cloud
Run instances that didn't handle that particular write). Fails open — a config_store
read error keeps the current engine rather than tearing down the pool.

**Client config sync (`connect/config_sync.py`).** `connect/` is a separate Windows
deployable with no direct Redis access, so `motion_min_area` / `motion_threshold` /
`motion_history` / `motion_var_threshold` / `fg_mask_threshold` /
`rtsp_reconnect_delay_sec` / `rtsp_connect_timeout_sec` had no path to ever reach it —
changing those sliders only ever affected the server-side YOLO/tracking gates, never
the actual camera client. `GET /api/config/client` (`backend/api/config.py`, protected
by the same `get_current_user` dependency the client already authenticates
`/api/triggers/*` with) now exposes just that seven-key subset.
`ClientConfigSync.run_forever()` polls it every 60s (first sync fires immediately on
`start()`, not after the first wait) and applies the result to the live
`MotionDetector`/`RTSPReader` instances — `MotionDetector.update_config()` rebuilds the
MOG2 background subtractor only when `motion_history`/`motion_var_threshold` actually
changed (rebuilding on every poll would reset the learned background and cause
spurious motion), the other three fields are read live on every `detect()` call so no
rebuild is needed. `RTSPReader.connect_timeout` is a new attribute (default 10.0s,
mirrors `rtsp_connect_timeout_sec`) that `connect()` falls back to when not given an
explicit `timeout` kwarg — `reconnect_delay` was already a plain settable attribute.
Wired into `VisionOSConnect.start()`/`stop()` in `connect/main.py` as a background
task alongside the main loop and WebSocket receive task.

### Clip-based dry-run testing (`backend/api/clip_analysis.py`, `clip_test.py`)

Two ways to run the real pipeline against a recorded clip instead of a live camera,
both used by the tuning dashboard to answer "if I change this slider, what changes":
- `POST /api/clip-analysis/upload` + `/{clip_id}/run` (SSE) — upload an MP4 (max
  200MB), server extracts frames (~10fps) and streams per-frame results.
- `POST /api/config/clip-test` — takes pre-extracted JPEGs from the browser, streams
  NDJSON (one JSON object per line: `meta` → `frame`* → `summary`), reports which
  pipeline stage (`yolo_gate` / `tracker` / `incident_builder` / `complete`) consumed
  or passed each frame. Hard ceiling of 90 frames (~30s @ 3fps) and 500KB/frame.

Both use a synthetic `camera_id` (e.g. `clip-analysis-{clip_id}`) so incident-builder
state stays isolated from production cameras, and both call
`cleanup_synthetic_camera()` in a `finally` block to avoid leaking that state. Both
share the global 8s Gemini rate limiter with production traffic — running a clip test
will add latency to real camera triggers that land during the same window.

### AI layer (`backend/ai/`)

`ai_client.py` is a single Vertex AI (`google-cloud-aiplatform`) client used for every
Gemini call — vision analysis, structured JSON analysis, incident decisions, NL query
answers, and daily/weekly digests. Auth is Application Default Credentials on Cloud
Run, not an API key (the `gemini_api_key` setting is legacy/unused post-migration to
Vertex AI). `analyse_frame_structured()` validates output against a controlled
vocabulary (event_type, threat_level, confidence) and discards results with
confidence < 0.6.

`reid_engine.py` does person re-identification via pgvector cosine similarity against
the `persons.embedding` column (0.72+ = confident match, 0.5–0.72 = ask Gemini as a
tiebreaker, <0.5 = mint a new `person_uid`). Note: BoxMOT/FastReID is commented out of
`requirements.txt` (numpy conflict) — embeddings currently come only from Gemini
appearance descriptions, not a dedicated embedding model. `identify()` persists every
match (new person or existing) via `_persist_sighting()` — `pipeline.py` already opened
a real DB session and passed it in, but `identify()` never wrote anything with it before
this was fixed, so every incident minted a brand-new `person_uid` regardless of history
and ghost detection / repeat-sighting escalation (both keyed on a `person_uid` recurring
across incidents) were silently non-functional in production.

`query_agent.py` is the NL query engine backing `POST /queries/natural` — a Gemini
function-calling agent (tools: `search_events`, `get_event_detail`,
`get_person_sightings`, bounded to 4 tool calls) reading real event data via
`HybridCRUD`. It replaced two things: `query_engine.py` (deleted — a fixed
intent-classify-then-hand-built-SQL pipeline that was dead code, never imported outside
its own test, and whose DB-fetch step was a stub that always returned `[]`), and the
substring-search implementation that actually was live in `backend/api/queries.py`
(zero LLM calls, despite being the "natural language query" endpoint). Tool set is
deliberately narrower than a first pass would suggest: `persons` / `person_sightings` /
`scene_states` reads looked like the obvious tool targets, but nothing in the live
pipeline populates `scene_states` at all, so a `get_scene_state` tool would query a
table with no writer.

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
digest Monday 08:00, retention cleanup daily 03:00 — `AsyncIOScheduler`, not the
`schedule` library). This wiring is recent — `apscheduler` had been a declared
dependency with no scheduler anywhere in the codebase, `backend/storage/cleanup.py`'s
`DataCleanup` had never been instantiated, and its deletion methods were literal
`# TODO: Implement with real SQLAlchemy query` stubs that always returned 0. Retention
days now come from `config_store` (`retention_free_days` / `retention_household_days`
/ `retention_business_days` / `transcript_retention_days`), not a hardcoded dict.
`auth.py` verifies Firebase ID tokens and exposes `get_current_user()` /
`require_tier()` dependencies used across `backend/api/`. Subscription tiers gate
features, but the vocabulary is genuinely inconsistent across the codebase, not just a
naming preference: `auth.py`'s `TIER_HIERARCHY` and the real billing logic in
`backend/api/payments.py` use `free`/`guard`/`guard_pro`, while `payment.html`'s
pricing page and `backend/core/pipeline.py`'s hardcoded alert-routing tier still say
`free`/`household`/`business` (299/499 BDT) — and `payments.py`'s actual guard price is
400 BDT, not 299. Don't assume either vocabulary is authoritative without checking
which one the specific code path you're touching actually uses.

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
- `doc/NUMERICAL_AUDIT.md` — authoritative, line-numbered inventory of every hardcoded
  threshold/timeout/limit in the codebase and what it controls, plus a "Critical
  Findings" section documenting known bugs (e.g. the two mismatches called out above).
  This is the source `config_store.DEFAULTS` was derived from — cross-check both when
  touching a threshold.
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
