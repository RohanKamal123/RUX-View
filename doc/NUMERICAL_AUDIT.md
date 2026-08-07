# Numerical Logic Audit — RUX View

**Date:** 2026-06-19  
**Scope:** Every file containing thresholds, intervals, timeouts, counts, scores, sizes, or hardcoded numeric constants that drive decision-making.

---

## SECTION 1 — Session & Trigger Thresholds

### FILE: `backend/api/triggers.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 38 | `_THREAT_ORDER` | `{"PENDING":-1,"LOW":0,"MEDIUM":1,"HIGH":2,"CRITICAL":3,"EMERGENCY":4}` | Ordinal threat comparison on line 301 — if new threat ordinal > session max threat, session escalates. `PENDING=-1` ensures the first Gemini result always outranks the initial placeholder. |
| 42 | `SESSION_TIMEOUT_SEC` | `180` | Session extend vs create decision (line 234). Frames within 180s of last motion extend the session; ≥180s creates a new session. Also used by the cleanup loop (line 78) to detect stale sessions. |
| 69 | Cleanup loop sleep | `15` | Seconds between cleanup loop iterations scanning for expired sessions. |
| 92 | `duration_sec=int(duration)` | truncation | Duration cast to int — sub-second durations are truncated (floor). |
| 405 | Motion diff_category ternary | `"trigger" if confidence > 0.5 else "skip"` | Legacy pipeline motion gate — above 0.5 = trigger, ≤0.5 = skip. |
| 634 | `limit` default (recent triggers) | `20` | Max events returned by `GET /api/triggers/recent`. |

---

## SECTION 2 — Incident Builder / Gemini Gating

### FILE: `backend/core/detection/incident_builder.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 7 | Docstring says | `120s` | **Bug: mismatch.** The docstring at line 7 and line 12 claim 120s periodic update, but... |
| 24 | `GEMINI_INTERVAL_SEC` | `60` | **Actual value.** Line 65: if `(now - last_call) >= 60`, a periodic Gemini update is triggered. Below 60s → skip. **Cost-critical.** |
| 65 | Periodic update check | `>= 60` | Enforces at least 60s between Gemini calls when tracks are present but no new objects appeared. |
| 50 | `_last_gemini_call.get(…, 0)` | `0` (epoch) | Default of 0 ensures the first call always passes the interval check. |
| 74 | Track count delta | `>= 2` | If track count changes by ±2 or more vs last evaluation, Gemini is called. A change of ±1 is ignored. |

---

## SECTION 3 — YOLO Detector

### FILE: `backend/core/detection/yolo_detector.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 33 | `CONFIDENCE_THRESHOLD` | `0.35` | Detection acceptance gate (line 171, 207). Objects with confidence ≥0.35 are retained; below are discarded. |
| 34 | `NMS_IOU_THRESHOLD` | `0.45` | Non-Maximum Suppression IoU threshold (line 208). Overlapping boxes with IoU >0.45: lower-confidence box suppressed. |
| 35 | `INPUT_SIZE` | `640` | YOLO ONNX model input resolution (640×640). Controls precision/performance tradeoff. |
| 88-89 | Thread counts | `2` each | `inter_op_num_threads=2`, `intra_op_num_threads=2` — CPU parallelism limits for edge hardware. |
| 316 | Annotated frame JPEG quality | `85` | JPEG quality for bounding-box-annotated frames sent to Gemini. |
| 131 | Padding colour | `(114, 114, 114)` | Grey padding value for letterbox resize. |

---

## SECTION 4 — BoT-SORT Tracker

### FILE: `backend/core/detection/botsort_tracker.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 23 | `TRACK_TTL_SECONDS` | `300` | Redis TTL on track state (line 146). Track data deleted if no updates for 300s. Matches `SESSION_TIMEOUT_SEC`. |
| 132 | Lost-track threshold | `30` | A track not matched in the current frame is "lost" only if `last_seen` is older than 30s. |
| 176 | `best_iou` (track match IoU) | `0.25` | Minimum IoU to match a detection to an existing track (line 179). Below 0.25 → new track. |
| 212 | Track ID format | `:03d` | Three-digit zero-padded sequential ID per camera. |

---

## SECTION 5 — Motion Detector

### FILE: `connect/camera/motion_detector.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 41 | `threshold` default | `0.05` | MOG2 sensitivity — lower values detect smaller motions. |
| 41 | `min_area` default | `8000` | Minimum contour area (px²) to count as motion (line 104). |
| 52 | `history` | `500` | MOG2 background model history (frames). |
| 52 | `varThreshold` | `56` | MOG2 variance threshold — higher = less sensitive to lighting changes. |
| 85 | FG mask threshold | `200` | Binary threshold applied to foreground mask — pixels <200 zeroed. |
| 88 | Kernel size | `(5, 5)` | 5×5 elliptical kernel for morphological operations (open/close). |

### FILE: `connect/camera/rtsp_reader.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 43 | `reconnect_delay` default | `5` | Seconds to wait between reconnection attempts (line 236). |
| 62 | `connect(timeout=10.0)` | `10.0` | Max seconds to wait for RTSP stream open. |
| 157 | Drain loop sleep | `0.001` | 1ms while loop yied when latest frame pending. |
| 194 | Thread join timeout | `2.0` | Max seconds to wait for drain thread to join during release. |

---

## SECTION 6 — Pipeline Gating

### FILE: `backend/core/pipeline.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 87 | `_VISION_THROTTLE_SECONDS` | `15` | **⚠️ Potential bug.** This is assigned to a local variable, NOT `self._vision_throttle_seconds`. Line 356 uses a hardcoded `15` literal instead. The variable is dead code — changing it has no effect. |
| 356 | Inline throttle check | `elapsed < 15` | Per-incident Gemini throttle (line 356). If fewer than 15s since last Gemini call for this incident → skip. |
| 182 | Brightness gate | `< 30` | Mean brightness below 30 → frame too dark, skip. |
| 191 | Blur gate | `< 50` | Laplacian variance below 50 → frame too blurry, skip. |
| 201 | Pixel diff threshold | `25` | Pixel intensity diff below 25 ignored in motion comparison. |
| 206 | Motion percent gate | `< 2.0%` | Less than 2% of pixels changed vs previous frame → skip. |
| 584 | Fallback threat level | `"MEDIUM"` | Default threat when incident decision fails. |

### FILE: `backend/core/pipeline_v2.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 130 | `"pixel_diff": 9999` | `9999` | Deliberate override — bypasses all pixel-diff thresholds when YOLO has confirmed relevant objects. |
| 82-83 | Default threat (YOLO blocked) | `"LOW"` | Threat level returned when YOLO gate blocks (no relevant objects). |
| 110-111 | Default threat (incident builder skip) | `"LOW"` | Threat level returned when incident builder says skip Gemini. |

---

## SECTION 7 — AI Client / Gemini

### FILE: `backend/ai/ai_client.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 38 | `_GEMINI_MIN_INTERVAL` | `8.0` | Global rate limiter for ALL Gemini calls (line 69). If last call was within 8.0s, the caller waits up to 8s then is either allowed or rejected. **Cost- and quota-critical.** |
| 166 | `_truncate_text` max words | `200` | Free-tier digest word limit (lines 983, 1010). |
| 403 | Confidence floor (structured) | `< 0.6` | If Gemini structured analysis returns confidence < 0.6 → silently discarded (returns `{}`). |
| 419 | Same floor on retry | `< 0.6` | Applied again on retry attempt. |
| 92 | Model name | `"gemini-2.5-flash"` | Gemini model variant — controls cost and response capability. |
| 45-46 | Project/region defaults | `"rux-view-497104"`, `"us-central1"` | Vertex AI project and region fallbacks. |
| — | `max_tokens` | Not set | No explicit output token limit — Gemini uses its default. |
| — | JPEG resize | None | JPEG bytes sent to Gemini as-is. |
| — | API retry count | 1 | `analyse_frame_structured` retries exactly once on validation failure (line 409). No additional retries. |

---

## SECTION 8 — Re-ID Engine

### FILE: `backend/ai/reid_engine.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 21 | `EXACT_MATCH_THRESHOLD` | `0.72` | Auto-match threshold (Tier 2, line 195). Cosine similarity ≥0.72 → auto-match without AI. |
| 22 | `UNCERTAIN_MIN` | `0.50` | Uncertainty zone lower bound (Tier 3, line 199). Score 0.50–0.72 → call Gemini tiebreaker. |
| 23 | `UNCERTAIN_MAX` | `0.72` | Upper bound (same as `EXACT_MATCH_THRESHOLD`). |
| 207 | Tiebreaker confidence boost | `(best_score + 0.9) / 2` | When Gemini says "same person", confidence = average of vector similarity and 0.90. |
| 84 | Crop resize | `(128, 256)` | Re-ID input dimensions (128×256). |
| 80 | Embedding dimension | `512` | FastReID ResNet50 output dimension. |
| 182, 216 | `find_similar limit` | `5` | Max candidate results from pgvector query. |

---

## SECTION 9 — Alert Routing

### FILE: `backend/alerts/alert_router.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 24 | `RETRY_INTERVAL` | `90` | Seconds between emergency alert retries (line 244). |
| 25 | `MAX_RETRIES` | `3` | Max retry attempts for emergency alerts (line 229). After 3 → escalate to secondary contact. |
| 63-81 | Routing switch | `LOW→log, MEDIUM→telegram_text, HIGH→telegram_photo, EMERGENCY→telegram_voice` | Channel selection by threat level. |

### FILE: `backend/alerts/telegram_client.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 33 | HTTP client timeout | `30.0` | Max seconds for Telegram API requests. |

---

## SECTION 10 — Database / Storage

### FILE: `backend/storage/engine.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 61 | `pool_size` | `3` | SQLAlchemy connection pool — max 3 persistent connections. |
| 62 | `max_overflow` | `2` | Max overflow connections (total = 5). |
| 63 | `pool_timeout` | `15` | Seconds to wait for a pooled connection before timeout. |
| 65 | `connect_args["timeout"]` | `15` | PostgreSQL connection timeout (asyncpg). |

### FILE: `backend/storage/pg_crud.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 251 | `threshold` default | `0.7` | Cosine distance threshold for pgvector `find_similar_persons`. |
| 252 | `limit` default | `10` | Max results from `find_similar_persons`. |
| 169 | `limit` default (events) | `50` | Default page size for `get_user_events`. |
| 458 | `limit` default (payments) | `20` | Default page size for `get_user_payments`. |

### FILE: `backend/storage/hybrid_crud.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 84 | `max_cameras` (QuotaInfo) | `20` | Max cameras per user. |
| 254 | `max_cam = 20` | `20` | Hardcoded max for quota calc. |
| 305 | `limit` default (events) | `50` | Default page size for `get_user_events`. |
| 464 | `limit` default (camera events) | `50` | Default page size for `get_camera_events`. |

---

## SECTION 11 — Ghost Detector / Repeat Sighting

### FILE: `backend/core/ghost_detector.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 43 | `_check_interval` | `60` | Periodic ghost check interval (line 154). |
| 84 | HIGH alert threshold | `1800` (30 min) | A person tracked ≥30 min without exit → HIGH alert. |
| 100 | MEDIUM alert threshold | `600` (10 min) | A person tracked ≥10 min without exit → MEDIUM alert. |

### FILE: `backend/core/repeat_sighting.py`

| Line | Name | Value | Controls |
|------|------|-------|----------|
| 23 | `RESET_TIMEOUT_HOURS` | `6` | If 6 hours (21600 s) since last sighting → count resets. |
| 26 | `NIGHT_START_HOUR` | `22` | Night hours start (10 PM). |
| 27 | `NIGHT_END_HOUR` | `6` | Night hours end (6 AM). |
| 141-156 | Daytime escalation | `1=none, 2=low, 3=medium, 4+=high` | Standard escalation by count. |
| 142-146 | Night escalation | `1=none, 2=medium, 3+=high` | Faster night escalation. |

---

## SECTION 12 — Tests (key numeric assertions)

### FILE: `backend/tests/unit/test_ai_client.py`

| Line | Assertion / Value | Purpose |
|------|-------------------|---------|
| 335 | `len(words) <= 200` | Free-tier digest word cap verification. |
| 351 | `len(words) > 200` | Business tier not truncated. |
| 432 | `result == {}` | Confidence <0.6 returns empty dict (silent discard). |
| 462 | `result["confidence"] == 0.72` | Valid retry result. |
| 479-480 | `result["threat_level"] == "LOW"`, `confidence == 0.0` | Safe fallback after double retry failure. |

### FILE: `backend/tests/unit/test_alerts.py`

| Line | Assertion | Purpose |
|------|-----------|---------|
| (search) | `retry_count == 3` | Confirms `MAX_RETRIES = 3`. |
| (search) | `telegram.send_text.call_count > 3` | Verifies retry escalation logic. |

### FILE: `backend/tests/unit/test_cleanup.py`

| Line | Assertion | Purpose |
|------|-----------|---------|
| (search) | `RETENTION_PERIODS["free"] == 7` | Free tier = 7 days. |
| (search) | `RETENTION_PERIODS["household"] == 30` | Household = 30 days. |
| (search) | `RETENTION_PERIODS["business"] == 90` | Business = 90 days. |
| (search) | `TRANSCRIPT_RETENTION_DAYS == 3` | Transcripts = 3 days. |

### FILE: `backend/tests/unit/test_clips.py`

| Line | Assertion | Purpose |
|------|-----------|---------|
| (search) | `max_clip_duration("household") == 30` | Household max clip = 30s. |
| (search) | `max_clip_duration("business") == 60` | Business max clip = 60s. |

### FILE: `backend/tests/unit/test_camera_limits.py`

| Line | Assertion | Purpose |
|------|-----------|---------|
| (search) | `MAX_CAMERAS_PER_USER == 20` | Global limit = 20. |
| (search) | `TIER_LIMITS[tier] == 20` | All tiers = 20. |

### FILE: `backend/tests/unit/test_cdn_manager.py`

| Line | Assertion | Purpose |
|------|-----------|---------|
| (search) | `CACHE_TTL_STATIC == 3600` | Static = 1 hour. |
| (search) | `CACHE_TTL_THUMBNAIL == 86400` | Thumbnails = 24 hours. |
| (search) | `CACHE_TTL_CLIP == 0` | Clips = no cache. |
| (search) | `CACHE_TTL_RECEIPT == 0` | Receipts = no cache. |

### FILE: `backend/tests/unit/test_motion.py`

| Line | Value | Purpose |
|------|-------|---------|
| 21 | `threshold=0.02, min_area=5000` | Custom test parameters (more sensitive than defaults). |
| 48 | `detector.threshold == 0.05` | Default threshold verification. |
| 49 | `detector.min_area == 8000` | Default min_area verification. |

---

## SECTION 13 — Config / Environment

### FILE: `backend/config.py`

| Line | Name | Default | Controls |
|------|------|---------|----------|
| 20 | `database_url` | `"postgresql+asyncpg://user:password@localhost:5432/visionos"` | Dev DB URL fallback. |
| 43 | `bkash_app_key` | `"01751549994"` | bKash phone number. |
| 47 | `bkash_sandbox` | `True` | Sandbox vs production. |
| 52 | `environment` | `"development"` | App environment. |
| 53 | `log_level` | `"INFO"` | Logging level. |
| 61 | `google_cloud_region` | `"asia-south1"` | Cloud Run region. |

### FILE: `.env.example`

Same defaults as `config.py`. No `JPEG_QUALITY`, `MIN_CONFIDENCE`, `MAX_EVENTS`, or `RETENTION_DAYS` env vars exist — all such values are hardcoded in source files as documented above.

---

## 🔴 Critical Findings

### 1. Docstring mismatch — `incident_builder.py` line 7 vs line 24
Line 7 and 12 mention `120s` periodic update interval, but the actual variable `GEMINI_INTERVAL_SEC` on line 24 is `60`. The enforcement at line 65 uses the 60s value.

### 2. Dead code — `pipeline.py` line 87
`_VISION_THROTTLE_SECONDS = 15` is assigned as a **local variable** inside `__init__()` (not `self._vision_throttle_seconds = 15`). It is never referenced anywhere. Line 356 uses a hardcoded `15` literal instead. Changing this variable has zero effect.

### 3. Three independent Gemini rate limiters
- **Global:** `_GEMINI_MIN_INTERVAL = 8.0s` in `ai_client.py` — applies to ALL Gemini calls site-wide.
- **Per-incident:** `15` (hardcoded) in `pipeline.py` — prevents rapid Gemini calls within the same incident.
- **Per-camera:** `GEMINI_INTERVAL_SEC = 60` in `incident_builder.py` — ensures at least 60s between camera-level evaluations.

These operate independently and can compound: a single camera could trigger all three wait periods sequentially.

### 4. No explicit `max_tokens` anywhere
All Gemini requests use the model's default output token limit. No capping is applied, which could lead to unpredictable response sizes.

### 5. No JPEG resize before Gemini
Images are sent to Gemini at whatever resolution the camera provides. For cameras above 720p, this consumes more Vertex AI usage than necessary.

### 6. Hardcoded camera limit
`max_cameras = 20` is hardcoded in two places (`hybrid_crud.py` lines 84, 254) and in `test_camera_limits.py` — not configurable via environment.

### 7. Risk: track count delta of ±2 is a low bar
`incident_builder.py` line 74: a change of just 2 tracks triggers a new Gemini call. In a busy scene with camera switching or partial occlusion, this may fire unnecessarily, multiplying costs.