# BUILD_PLAN.md
# Vision OS — Solo Build Roadmap
# 12 Weeks from Zero to Beta

---

## How to Use This Document

Each phase has:
- What to build
- Which Claude context to use
- What "done" looks like (tests passing)
- The CONTEXT.md to write before starting

Rule: Do not start Phase N+1 until Phase N tests are green.

---

## Pre-Build Setup (Day 1 — Before Any Code)

```
[ ] Create GitHub repo: vision-os
[ ] Set up folder structure (all folders, no files yet)
[ ] Create requirements.txt (all dependencies listed)
    Key additions vs original plan:
      google-generativeai  (Gemini 2.0 Flash — replaces Vertex AI SDK)
      boxmot               (Re-ID — replaces torchreid)
      pgvector             (via psycopg2 — vector similarity in Postgres)
      kokoro               (TTS for voice notes — replaces gTTS)
      apscheduler          (async job scheduler — replaces schedule)
      nuitka               (Windows build — replaces PyInstaller, dev only)
[ ] Set up .env.example (all env vars documented)
[ ] Create GitHub Actions test.yml (pytest runs on push)
[ ] Set up Google Cloud project
[ ] Enable Gemini API (NOT Vertex AI — use google-generativeai SDK directly)
[ ] Set up Cloud SQL Postgres instance
[ ] Enable pgvector extension on Cloud SQL instance
[ ] Set up Firebase project
[ ] Get OpenAI API key (Whisper)
[ ] Set up Telegram Bot (@BotFather)
[ ] Create SSL Wireless BD account
[ ] Write CONTEXT.md for every module folder
[ ] Commit: "chore: project skeleton"
```

---

## PHASE 1 — FOUNDATION
### Week 1–2

Goal: Every module stubbed. Database exists.
      All tests written (failing is fine).
      CI pipeline running.

---

### Sprint 1.1 — Database Schema
**Claude context:** backend/storage/CONTEXT.md
**File:** backend/storage/database.py

```
Tasks:
[ ] Write all CREATE TABLE statements
[ ] Write index definitions
[ ] Write get_db() connection helper
[ ] Write basic CRUD for each table
[ ] Alembic migrations setup
[ ] Enable pgvector extension (see D022):
    CREATE EXTENSION IF NOT EXISTS vector;
    ALTER TABLE persons ADD COLUMN embedding vector(512);
    CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops);

Tests (test_database.py):
[ ] test_create_all_tables()
[ ] test_insert_event()
[ ] test_insert_person()
[ ] test_insert_person_with_embedding()
[ ] test_pgvector_similarity_query()
[ ] test_insert_scene_state()
[ ] test_insert_shop_analytics()
[ ] test_user_tier_query()

Done when: all tests green, tables exist in Cloud SQL,
           pgvector similarity query returns correct person
```

---

### Sprint 1.2 — Firebase Auth Middleware
**Claude context:** backend/dashboard/CONTEXT.md
**File:** backend/dashboard/auth.py

```
Tasks:
[ ] Firebase Admin SDK initialisation
[ ] verify_token() middleware function
[ ] get_current_user() dependency for FastAPI
[ ] Tier check decorator (require_tier)

Tests (test_auth.py):
[ ] test_valid_token_passes()
[ ] test_invalid_token_rejected()
[ ] test_tier_check_household()
[ ] test_tier_check_business()
[ ] test_free_tier_blocked_premium_route()

Done when: auth middleware protects routes correctly
```

---

### Sprint 1.3 — Unified AI Client
**Claude context:** backend/ai/CONTEXT.md
**File:** backend/ai/ai_client.py  ← single file (previously split into gemma_client.py + gemini_client.py — see D001)

```
Setup:
[ ] pip install google-generativeai
[ ] Configure: genai.configure(api_key=GEMINI_API_KEY)
[ ] Model: gemini-2.0-flash (handles both vision + reasoning)

Tasks — Vision functions (previously in gemma_client.py):
[ ] analyse_frame(jpeg_bytes) → dict
    (person description, clothing, objects, actions, threat_level)
[ ] analyse_frame_detailed(jpeg_bytes) → dict  (NL query mode)
[ ] analyse_shop_entry(jpeg_bytes) → dict
    (gender_estimate, age_estimate, clothing, entry_zone)

Tasks — Reasoning functions (previously in gemini_client.py):
[ ] make_incident_decision(timeline, context) → dict
[ ] answer_query(question, events, analyses) → str
[ ] answer_scene_state(question, world_state) → str
[ ] generate_daily_digest(events, tier) → str
[ ] reid_tiebreaker(emb1_desc, emb2_desc) → dict  (uncertainty zone)

Tasks — Audio:
[ ] transcribe_audio(audio_bytes) → str  (OpenAI Whisper — unchanged)

All mock responses in fixtures/mock_responses/ai_client/

Tests (test_ai_client.py):
[ ] test_analyse_frame_returns_required_fields()
[ ] test_analyse_frame_detailed_prompt_parse()
[ ] test_shop_entry_returns_demographics()
[ ] test_incident_decision_parse()
[ ] test_query_answer_format()
[ ] test_digest_under_200_words_free_tier()
[ ] test_reid_tiebreaker_returns_match_bool()
[ ] test_whisper_transcription()
[ ] test_invalid_response_handled_gracefully()

Done when: all functions return correct types,
           one client file only, graceful error handling confirmed
```

---

### Sprint 1.4 — API Stubs
**Claude context:** backend/api/CONTEXT.md
**Files:** triggers.py, cameras.py, users.py, queries.py

```
Tasks:
[ ] POST /triggers/frame — receive JPEG trigger
[ ] POST /triggers/audio — receive audio trigger
[ ] GET  /cameras — list user's cameras
[ ] POST /cameras — add camera
[ ] PUT  /cameras/{id} — update camera config
[ ] GET  /users/me — current user info
[ ] POST /queries — submit NL query
[ ] GET  /events — list events with filters
[ ] GET  /persons/{id} — person profile

All routes stubbed with TODO bodies
All routes protected with auth middleware

Tests:
[ ] test_trigger_endpoint_accepts_jpeg()
[ ] test_trigger_endpoint_rejects_unauthenticated()
[ ] test_camera_crud()
[ ] test_query_endpoint_requires_premium()

Done when: all endpoints return correct status codes
           even if logic is not implemented
```

---

## PHASE 2 — CLIENT AGENT
### Week 3–4

Goal: Vision OS Connect works on real camera.
      Sends triggers to backend. Buffer works offline.

---

### Sprint 2.1 — RTSP Reader + Frame Selector
**Claude context:** connect/camera/CONTEXT.md
**Files:** rtsp_reader.py, frame_selector.py

```
Tasks:
[ ] cv2.VideoCapture RTSP connection
[ ] reconnect on drop (retry with backoff)
[ ] frame_generator() yields frames continuously
[ ] select_best_frame(frames: list) → frame
    (score by largest person-shaped contour area)
[ ] capture_best_frame(stream, n=8) → jpeg_bytes

Tests (use saved test video or local webcam):
[ ] test_rtsp_connection_local()
[ ] test_reconnect_on_drop()
[ ] test_frame_selector_picks_highest_score()
[ ] test_jpeg_encoding()

Done when: can connect to real IP camera RTSP,
           reads frames, selects best frame
```

---

### Sprint 2.2 — Motion Detector
**Claude context:** connect/camera/CONTEXT.md
**File:** connect/camera/motion_detector.py

```
Tasks:
[ ] pixel_diff(frame1, frame2) → int
[ ] apply_ignore_zones(frame, zones) → masked_frame
[ ] contour_filter(contours, min_area, mode) → filtered
[ ] aspect_ratio_filter(contour) → bool
[ ] MotionDetector class with:
    → process(frame) → MotionResult
    → MotionResult.should_trigger: bool
    → MotionResult.pixel_diff: int
    → MotionResult.largest_contour_area: int
    → MotionResult.diff_category: str (skip/check/gemma/urgent)
[ ] Parameters by mode (indoor/outdoor/parking/mixed/shop)

Tests (use test_frames/ fixtures):
[ ] test_no_motion_returns_false()
[ ] test_large_motion_returns_true()
[ ] test_ignore_zone_masks_motion()
[ ] test_aspect_ratio_filters_wide_objects()
[ ] test_diff_categories_per_mode()
[ ] test_outdoor_higher_threshold()

Done when: correctly filters on 20 test frame pairs
```

---

### Sprint 2.3 — YAMNet Audio Detector
**Claude context:** connect/audio/CONTEXT.md
**Files:** audio_capture.py, yamnet_detector.py

```
Tasks:
[ ] AudioCapture: record 8s chunks on threshold
[ ] RMS amplitude threshold (configurable)
[ ] YAMNet model load (TensorFlow)
[ ] classify_audio(audio_chunk) → YAMNetResult
    → class_name, confidence, should_send_to_whisper
[ ] Thresholds per class (glass/gunshot/shout/etc)

Tests (use test_audio/ fixtures):
[ ] test_silence_below_threshold()
[ ] test_loud_sound_above_threshold()
[ ] test_yamnet_classifies_glass_breaking()
[ ] test_yamnet_classifies_speech()
[ ] test_confidence_threshold_gates_whisper()

Done when: correctly classifies 10 test audio clips
```

---

### Sprint 2.4 — Transport + Buffer
**Claude context:** connect/transport/CONTEXT.md
**Files:** websocket_client.py, trigger_sender.py, local_queue.py, sms_sender.py

```
Tasks:
[ ] WebSocket persistent connection to backend
[ ] heartbeat every 30s
[ ] reconnect on drop (exponential backoff)
[ ] send_trigger(jpeg_bytes, audio_bytes, meta) → bool
[ ] LocalQueue (SQLite):
    → enqueue(trigger_data)
    → flush_to_server() on reconnect
    → max 500 events, drop oldest
    → 48hr TTL
[ ] SSL Wireless SMS:
    → send_sms(phone, message) for HIGH during outage

Tests:
[ ] test_trigger_sends_on_internet_up()
[ ] test_trigger_queues_on_internet_down()
[ ] test_queue_flushes_on_reconnect()
[ ] test_queue_drops_oldest_at_capacity()
[ ] test_sms_sends_for_high_threat_outage()

Done when: works with real backend, offline buffer confirmed
```

---

### Sprint 2.5 — Windows App Packaging
**Claude context:** connect/CONTEXT.md
**Files:** main.py, config.py, ui/tray_app.py

```
Tasks:
[ ] Config storage (JSON, survives restart)
[ ] System tray icon (running/stopped/error states)
[ ] Right-click menu: Open settings, Stop, Exit
[ ] Settings window: API key, camera name, RTSP URL, mode
[ ] QR code scan → auto-fill API key
[ ] Nuitka build spec (see D025 — NOT PyInstaller)
    nuitka --onefile --windows-icon=icon.ico
           --windows-product-name="Vision OS Connect"
           --enable-plugin=tk-inter
           main.py
[ ] Build .exe via Nuitka
[ ] Verify no Windows Defender false-positive on output binary

Note: Nuitka requires C compiler (MinGW-w64 on Windows, set up once).
      Build takes ~4 min vs PyInstaller's 30s — expected and acceptable.

Manual test (no automated):
[ ] Install on Windows PC
[ ] Connect to real IP camera
[ ] Verify trigger reaches backend
[ ] Verify tray icon shows correct state
[ ] Confirm Windows Defender does not flag the binary

Done when: .exe installs, runs, sends first trigger,
           no antivirus false-positive on clean Windows install
```

---

## PHASE 3 — CORE INTELLIGENCE
### Week 5–6

Goal: Full incident pipeline working end to end.
      Real camera → Gemma analysis → Telegram alert.

---

### Sprint 3.1 — Incident Tracker
**Claude context:** backend/core/CONTEXT.md
**File:** backend/core/incident_tracker.py

```
Tasks:
[ ] CamState enum: IDLE / TRACKING / CLOSE
[ ] IncidentTracker class per camera:
    → process(trigger) → IncidentAction | None
    → actions: GEMMA_CALL / BURST / CLOSE_INCIDENT
[ ] All timing parameters by mode
[ ] Pixel diff category → action mapping
[ ] Loitering escalation timers
[ ] Night mode parameter switching
[ ] Burst interval logic (normal/high/urgent)

Tests:
[ ] test_idle_transitions_to_tracking_on_trigger()
[ ] test_tracking_closes_on_no_motion()
[ ] test_burst_fires_at_correct_interval()
[ ] test_loitering_escalates_at_correct_times()
[ ] test_night_mode_halves_cooldown()
[ ] test_max_cap_closes_incident()
[ ] test_gemma_skip_on_no_change()
[ ] test_urgent_overrides_cooldown()

Done when: all 50+ test scenarios pass
```

---

### Sprint 3.2 — Camera Modes
**Claude context:** backend/modes/CONTEXT.md
**Files:** indoor_mode.py, outdoor_mode.py, parking_mode.py,
           mixed_mode.py (one file each, max 200 lines)

```
Tasks per mode file:
[ ] get_motion_params(mode) → MotionParams
[ ] get_timing_params(mode) → TimingParams
[ ] get_loiter_params(mode, location_type) → LoiterParams
[ ] should_analyse_individual(mode, zone) → bool
[ ] parking_mode.py: vehicle detection logic
[ ] outdoor_mode.py: MOG2 background subtractor setup
[ ] mixed_mode.py: zone crossing detection

Tests:
[ ] test_indoor_lower_thresholds_than_outdoor()
[ ] test_parking_vehicle_trigger_logic()
[ ] test_outdoor_mog2_baseline_learns()
[ ] test_mixed_zone_crossing_triggers()
[ ] test_shop_floor_loiter_disabled_business_hours()

Done when: each mode returns correct params for each scenario
```

---

### Sprint 3.3 — Re-ID Engine
**Claude context:** backend/ai/CONTEXT.md
**File:** backend/ai/reid_engine.py

```
Setup:
[ ] pip install boxmot
[ ] Backend: BoT-SORT tracker + FastReID embedding (see D007)
[ ] pgvector extension enabled on Cloud SQL (see D022)

Tasks:
[ ] crop_person(frame, bbox_normalized) → crop
[ ] extract_embedding(crop) → np.array (512-dim, FastReID backend)
[ ] cosine_similarity via pgvector: SQL query with <-> operator
    (replaces Python-side numpy loops)
[ ] appearance_signature(ai_client_person_result) → str
[ ] string_similarity(sig1, sig2) → float
[ ] ReIDEngine.identify(frame, person_result) → str
    → returns PERSON_XXX (existing or new)
    → queries Postgres: SELECT id FROM persons
      ORDER BY embedding <-> %s LIMIT 5
[ ] Store new embeddings: INSERT with vector column
[ ] Uncertain zone (0.5–0.72 cosine) → ai_client.reid_tiebreaker()

Database schema addition (Sprint 1.1 migration):
[ ] ALTER TABLE persons ADD COLUMN embedding vector(512)
[ ] CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops)

Tests (use test_frames/ with known pairs):
[ ] test_same_person_different_frames_matches()
[ ] test_different_people_dont_match()
[ ] test_new_person_gets_new_id()
[ ] test_pgvector_similarity_query_returns_correct_person()
[ ] test_uncertain_zone_calls_ai_client_tiebreaker()
[ ] test_appearance_signature_format()

Done when: correctly matches 8/10 test person pairs
           pgvector query confirmed faster than Python loop
```

---

### Sprint 3.4 — Cross-Camera + Ghost Detection
**Claude context:** backend/core/CONTEXT.md
**Files:** cross_camera.py, ghost_detector.py, repeat_sighting.py

```
Tasks (cross_camera.py):
[ ] CameraTopology: load from user config
[ ] get_neighbours(camera_id) → list
[ ] check_cross_camera_match(person_id, timestamp,
                              current_camera) → CrossCameraResult
[ ] detect_impossible_timing(person_id, cam_a, cam_b,
                              time_gap) → bool

Tasks (ghost_detector.py):
[ ] track_entry(person_id, camera_id, timestamp)
[ ] check_unaccounted() → list of GhostAlerts
[ ] cancel_ghost(person_id)
[ ] Timers: 10min MEDIUM, 30min HIGH

Tasks (repeat_sighting.py):
[ ] record_sighting(person_id, user_id, timestamp)
[ ] get_today_count(person_id, user_id) → int
[ ] get_escalation_level(count, is_night) → str
[ ] should_reset(last_seen, is_night) → bool

Tests:
[ ] test_cross_camera_matches_within_window()
[ ] test_cross_camera_misses_outside_window()
[ ] test_impossible_timing_flagged()
[ ] test_ghost_alert_fires_at_10_min()
[ ] test_ghost_alert_fires_at_30_min()
[ ] test_ghost_cancelled_on_sighting()
[ ] test_repeat_escalation_1st_to_4th()
[ ] test_repeat_resets_after_6_hours()
[ ] test_repeat_never_resets_at_night()

Done when: all cross-camera tests pass with mock topology
```

---

### Sprint 3.5 — Alert Router + Telegram
**Claude context:** backend/alerts/CONTEXT.md
**Files:** alert_router.py, telegram_client.py, voice_note.py, sms_client.py

```
Tasks (alert_router.py):
[ ] route_alert(incident, user, tier) → AlertAction
[ ] LOW → log only
[ ] MEDIUM → telegram text
[ ] HIGH → telegram photo + caption
[ ] EMERGENCY → telegram urgent + voice note
[ ] retry logic (90s, max 3 attempts)
[ ] secondary contact escalation

Tasks (telegram_client.py):
[ ] send_text(chat_id, message)
[ ] send_photo(chat_id, jpeg_bytes, caption)
[ ] send_voice(chat_id, ogg_bytes, caption)
[ ] Plain text format (NO markdown — timestamp underscores)
[ ] Message templates per alert type

Tasks (voice_note.py):  ← uses Kokoro-82M, NOT gTTS/pyttsx3 (see D023)
[ ] pip install kokoro
[ ] Load kokoro model once at startup (singleton)
[ ] generate_voice_note(camera_name, timestamp, threat_summary) → ogg_bytes
[ ] Text template: "{camera_name}. {timestamp}. {threat_summary}."
[ ] Convert Kokoro WAV output → OGG Opus (ffmpeg) for Telegram

Tasks (sms_client.py):
[ ] send_sms(phone, message) via SSL Wireless API

Tests:
[ ] test_low_threat_logs_only()
[ ] test_medium_sends_telegram_text()
[ ] test_high_sends_telegram_photo()
[ ] test_emergency_sends_voice_note()
[ ] test_voice_note_returns_ogg_bytes()
[ ] test_plain_text_no_markdown()
[ ] test_retry_on_telegram_failure()

Done when: real Telegram message received on test phone,
           voice note plays naturally (not robotic)
```

---

### Sprint 3.6 — Pipeline Orchestrator
**Claude context:** backend/core/CONTEXT.md
**File:** backend/core/pipeline.py

```
Tasks:
[ ] CameraPipeline class (one per camera)
[ ] process_trigger(jpeg_bytes, audio_bytes, meta)
[ ] Orchestrates:
    incident_tracker → gemma → reid → cross_camera
    → repeat_sighting → ghost_detector → gemini_decision
    → alert_router → database
[ ] Handles all camera modes
[ ] Async (FastAPI background tasks)

Integration test (test_pipeline_flow.py):
[ ] test_full_indoor_incident_low()
[ ] test_full_indoor_incident_high()
[ ] test_full_parking_incident()
[ ] test_audio_visual_correlation()
[ ] test_cross_camera_person_tracking()
[ ] test_repeat_sighting_escalation_to_emergency()
[ ] test_ghost_detection_full_flow()

Done when: end-to-end test passes with real camera + Telegram
```

---

## PHASE 4 — AUDIO + BUSINESS FEATURES
### Week 7–8

---

### Sprint 4.1 — Audio Intelligence
**Claude context:** backend/ai/CONTEXT.md
**Files:** backend already has whisper_client.py (from Phase 1)
          Add: audio correlation logic to pipeline.py

```
Tasks:
[ ] Audio-visual correlation (±15s window)
[ ] audio_only_incident() when no visual match
[ ] Whisper transcript + Gemini interpretation flow
[ ] Dashboard display: transcript + interpretation
[ ] Transcript expiry job (1-3 days)

Tests:
[ ] test_audio_correlates_with_open_incident()
[ ] test_audio_only_when_no_visual()
[ ] test_whisper_bangla_transcript()
[ ] test_transcript_expires_after_3_days()

Done when: Bangla audio triggers and transcribes correctly
```

---

### Sprint 4.2 — Shop / Analytics Mode
**Claude context:** backend/modes/CONTEXT.md
**File:** backend/modes/shop_mode.py
**File:** backend/analytics/shop_analytics.py

```
Tasks (shop_mode.py):
[ ] Business hours check
[ ] Entrance zone detection
[ ] Staff filter (Re-ID based)
[ ] Customer entry event trigger
[ ] After-hours → security mode switch

Tasks (shop_analytics.py):
[ ] record_customer_entry(camera_id, gemma_result)
[ ] aggregate_hourly(camera_id, date)
[ ] get_daily_summary(camera_id, date) → dict
[ ] get_peak_hours(camera_id, date) → list
[ ] get_demographic_breakdown(camera_id, date) → dict

Tests:
[ ] test_staff_not_counted_as_customer()
[ ] test_customer_counted_on_entrance_zone()
[ ] test_shop_floor_loiter_not_triggered()
[ ] test_after_hours_switches_to_security()
[ ] test_hourly_aggregation()
[ ] test_demographic_breakdown_totals()

Done when: shop demo: 10 entries → correct count + breakdown
```

---

### Sprint 4.3 — Digest Generator
**Claude context:** backend/analytics/CONTEXT.md
**File:** backend/analytics/digest_generator.py

```
Tasks:
[ ] generate_daily_digest(user_id, date, tier) → str
[ ] generate_weekly_digest(user_id, week_start, tier) → str
[ ] free_digest() → short Telegram message
[ ] household_digest() → detailed + person stats
[ ] business_digest() → + shop analytics

Scheduling — use APScheduler AsyncIOScheduler (see D024, NOT `schedule` library):
[ ] pip install apscheduler
[ ] Initialise AsyncIOScheduler in FastAPI lifespan startup
[ ] Daily digest: cron trigger at 22:00 user local time
[ ] Weekly digest: cron trigger Monday 08:00
[ ] Transcript cleanup: cron trigger daily 03:00 (links to Sprint 5.4)
[ ] All jobs backed by Postgres jobstore (handles restarts)

Tests:
[ ] test_free_digest_under_200_words()
[ ] test_household_digest_includes_person_stats()
[ ] test_business_digest_includes_analytics()
[ ] test_digest_sends_to_telegram()
[ ] test_apscheduler_job_registered_on_startup()

Done when: daily digest sends to test Telegram correctly,
           scheduler confirmed async (does not block FastAPI)
```

---

## PHASE 5 — DASHBOARD + QUERIES
### Week 9–10

---

### Sprint 5.1 — Dashboard Core
**Claude context:** backend/dashboard/CONTEXT.md
**Files:** server.py, templates/*.html, static/

```
Pages to build:
[ ] index.html — event feed, all cameras, filter by camera
[ ] camera.html — per-camera event list
[ ] person.html — person profile (sightings timeline)
[ ] settings.html — camera config, ignore zones editor
[ ] login.html — Firebase Auth flow

Features:
[ ] Cookie/JWT session after Firebase verify
[ ] Auto-refresh event feed (30s)
[ ] Thumbnail display per event
[ ] Threat level badges (colour coded)
[ ] Per-camera filter tabs
[ ] Mobile responsive (users check on phone)

Tests:
[ ] test_dashboard_requires_auth()
[ ] test_event_feed_returns_correct_user_events()
[ ] test_person_profile_shows_sightings()
[ ] test_tier_gates_premium_pages()

Done when: dashboard usable on mobile browser
```

---

### Sprint 5.2 — NL Query Engine
**Claude context:** backend/ai/CONTEXT.md
**File:** backend/ai/query_engine.py
**File:** backend/templates/query.html

```
Tasks (query_engine.py):
[ ] parse_query_intent(question) → QueryIntent
    (appearance / object / scene_state / behaviour /
     cross_camera / timeline)
[ ] build_sql_filter(intent) → SQL WHERE clause
[ ] fetch_matching_events(filter) → list
[ ] fetch_gemma_analyses(event_ids) → list
    (from stored JSON or re-analyse thumbnail)
[ ] synthesise_answer(question, events, analyses) → str
[ ] Return: answer_text + matching_thumbnails

Tasks (query.html):
[ ] Text input for question
[ ] Submit button
[ ] Loading state
[ ] Answer display
[ ] Thumbnail grid of matches
[ ] Only shown to Household/Business tier

Tests:
[ ] test_appearance_query_finds_red_shirt()
[ ] test_behaviour_query_finds_running()
[ ] test_scene_state_query_returns_gate_status()
[ ] test_timeline_query_returns_ordered_events()
[ ] test_free_tier_blocked_from_queries()

Done when: "who wore red today?" returns correct result
```

---

### Sprint 5.3 — bKash Billing
**Claude context:** backend/billing/CONTEXT.md
**File:** backend/billing/bkash_client.py

```
Tasks:
[ ] bKash payment initiation
[ ] Payment verification webhook
[ ] Subscription creation (per camera)
[ ] Trial start/end logic
[ ] Tier upgrade/downgrade
[ ] Grace period (7 days after trial)
[ ] Telegram warning messages (day 1, 5, 7)
[ ] Camera disable on non-payment

Tests (use bKash sandbox):
[ ] test_payment_initiation()
[ ] test_webhook_verification()
[ ] test_trial_starts_on_signup()
[ ] test_tier_upgrades_on_payment()
[ ] test_grace_period_data_retained()
[ ] test_cameras_disabled_after_grace()

Done when: test payment flow completes in sandbox
```

---

### Sprint 5.4 — Data Retention + Cleanup
**Claude context:** backend/storage/CONTEXT.md
**File:** backend/storage/cleanup.py

```
Tasks:
[ ] delete_old_events(user_id, days) — by tier
    Free: 7 days
    Household: 30 days
    Business: 90 days
[ ] delete_expired_transcripts() — 1-3 days
[ ] delete_old_thumbnails() — matches event retention
[ ] Run daily at 3am (schedule library)
[ ] Log deletions for audit

Tests:
[ ] test_free_events_deleted_after_7_days()
[ ] test_household_events_kept_30_days()
[ ] test_transcripts_deleted_after_3_days()
[ ] test_cleanup_doesnt_delete_wrong_user()

Done when: cleanup runs and correct data deleted
```

---

## PHASE 6 — STABILITY + BETA
### Week 11–12

---

### Sprint 6.1 — Edge Cases + Hardening

```
Known edge cases to handle:
[ ] Camera goes offline mid-incident
[ ] Gemma returns invalid JSON
[ ] Re-ID bbox outside frame bounds
[ ] Whisper returns empty transcript
[ ] bKash webhook arrives twice (idempotency)
[ ] Cross-camera topology has cycle
[ ] User deletes camera with active incident
[ ] New user with no cameras hits dashboard
[ ] Trial expires during active incident
[ ] 500 events in buffer, more arrive
[ ] Telegram bot rate limited
[ ] Postgres connection pool exhausted

For each: write test → handle gracefully → retest
```

---

### Sprint 6.2 — Multi-Location Testing

```
Test scenario:
User has 3 locations, 5 cameras total
[ ] All cameras trigger simultaneously
[ ] Cross-camera within one location works
[ ] Cross-camera DOES NOT cross between locations
[ ] Ghost detection per location independent
[ ] Digest covers all locations

Use: multiple test camera streams
```

---

### Sprint 6.3 — Android Viewer App

```
Thin client only — viewer, no processing

Screens:
[ ] Login (Firebase Auth)
[ ] Camera list (all locations)
[ ] Event feed
[ ] Event detail (thumbnail + analysis)
[ ] Person profile
[ ] Notifications (FCM push)
[ ] Basic settings

Tech: Kotlin, Retrofit, Firebase, FCM, Glide

Done when: push notification arrives on phone,
           tap opens correct event in dashboard
```

---

### Sprint 6.4 — Beta Onboarding (5–10 Real Users)

```
Beta criteria:
[ ] 3+ real homeowners with real IP cameras
[ ] 2+ shop owners (business tier test)
[ ] 1 godown owner
[ ] Minimum 1 week of real usage each
[ ] Collect: false positive rate, missed incidents,
             daily digest feedback, query accuracy

Fix list from beta:
[ ] Anything that causes missed HIGH alert = P0 fix
[ ] False positive > 5/day = tune parameters
[ ] Query wrong answer > 30% = improve prompt
[ ] App crashes = P0 fix
[ ] Digest not useful = rewrite prompt

Done when: 5 users have gone 7 days without P0 issue
```

---

## CONTEXT.md Template (Copy for Each Module)

```markdown
# CONTEXT.md — [Module Name]

## What This Module Does
[One paragraph description]

## Inputs
[Function signatures with types]

## Outputs
[Return types and structures]

## Dependencies
[Other modules this calls]

## Called By
[Other modules that call this]

## Key Decisions
[Any decisions specific to this module]

## Known Limitations
[What this doesn't handle]

## Test Fixtures Available
[List of test frames/audio/JSON available]
```

---

## Daily Routine (Solo Build)

```
Morning (30 min):
  → Read yesterday's DECISIONS.md additions
  → Pick ONE task from current sprint
  → Write CONTEXT.md for that module if not done

Coding (main session):
  → Paste CONTEXT.md + relevant ARCHITECTURE.md section to Claude
  → Ask for: function + test + docstring in one response
  → Run tests
  → Fix failures
  → Commit when green

End of day (15 min):
  → Update DECISIONS.md if any new choices made
  → Update BUILD_PLAN.md checkboxes
  → Commit: "feat: [module] [what was done today]"
  → Note any blockers for tomorrow
```

---

*BUILD_PLAN.md — Vision OS V1*
*Update checkboxes as tasks complete*
*Never skip the tests. Never.*
