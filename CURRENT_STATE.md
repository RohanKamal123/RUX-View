# Current State

Last verified: 2026-09-22. Update this file whenever a feature moves between these three sections — do not let it go stale.

## Working

- YOLOv8n detection gate — `backend/core/detection/yolo_detector.py`, `connect/models/yolov8n.onnx` — runs ONNX Runtime inference on trigger frames and returns bounding boxes, confidence, and class labels when the model is available.
- IoU track continuity — `backend/core/detection/botsort_tracker.py`, `backend/core/pipeline_v2.py` — assigns Redis-backed track IDs by bounding-box IoU; this is not ByteTrack and is not a person-identity system.
- Trigger ingestion — `backend/api/triggers.py` — accepts authenticated frame and audio triggers and sends them through the configured pipeline.
- Incident tracking and timelines — `backend/core/incident_tracker.py`, `backend/core/pipeline.py` — groups trigger observations into incidents and builds a per-incident timeline.
- Gemini vision and incident decisions — `backend/ai/ai_client.py`, `backend/core/pipeline.py` — analyzes frames/audio and produces structured threat decisions.
- Alert routing — `backend/alerts/alert_router.py`, `backend/alerts/telegram_client.py` — routes configured threat alerts to the dashboard/Telegram channels.
- Event persistence — `backend/api/triggers.py`, `backend/storage/hybrid_crud.py`, `backend/storage/pg_crud.py`, `backend/storage/database.py` — creates one event through the API path and updates `timeline_json` on the same event.
- Firebase authentication — `backend/dashboard/auth.py`, `backend/api/*.py` — verifies Firebase ID tokens in production; development mode intentionally uses the documented dev bypass.
- WebSocket authentication and CORS — `backend/dashboard/server.py` — verifies the WebSocket token through the shared auth code and uses an explicit trusted-origin list.
- PostgreSQL storage — `backend/storage/database.py`, `backend/storage/pg_crud.py` — stores users, cameras, locations, events, and event metadata in PostgreSQL when configured.
- Camera connectivity and trigger client — `connect/` — reads configured camera streams, performs client-side motion/audio triggering, and posts trigger data to the backend.
- Natural-language event queries — `backend/api/queries.py`, `backend/ai/query_engine.py` — provides the existing authenticated query path over stored events; it is not a task/rule automation system.

## Stubbed / Disabled

- Signup and password reset — `backend/api/public_signup.py` — validation-only in-memory prototype; fabricates a Firebase UID, stores users/codes in process memory, and does not create Firebase accounts, persist users, or send messages.
- Analytics — `backend/api/analytics.py` — authenticated endpoints return placeholder zero/empty values; refresh returns a placeholder success response and does not run aggregation.
- Clip listing, playback, thumbnails, and recording — `backend/api/clips.py` — tier checks run, but listing returns an empty list and playback/thumbnail/recording routes return fabricated placeholder responses rather than media operations.
- Re-ID fallback dependency — `backend/ai/reid_engine.py` — BoxMOT is unavailable in the declared dependencies; the legacy module remains in the tree and is referenced by the pipeline, so identity matching must not be treated as a reliable supported feature.
- Advanced analytics modules — `backend/analytics/` — contain supporting code/design surfaces, but the public analytics API is not wired to real aggregation results.

## Not Built Yet

- Supported Person Re-ID / persistent identity matching — no reliable v1 capability. `backend/ai/reid_engine.py` has not actually been removed yet and remains a legacy call site; remove it before claiming this item is complete.
- ByteTrack replacement — no ByteTrack implementation is present. The current tracker module is `backend/core/detection/botsort_tracker.py`, an IoU-based Redis-backed tracker, and should not be described as ByteTrack.
- Line-crossing or zone-entry/exit detection — no geometric line/zone event logic exists in the pipeline.
- Cross-camera time-window correlation — no supported production implementation should be assumed.
- Natural-language rule parsing/tasking — query handling exists, but rule creation, scheduled tasks, and action automation do not.
- Crowd detection/counting — explicitly out of scope for v1; no supported crowd detector is wired into the trigger path.
- Production clip storage/playback — no real clip recorder/player path is connected to the public clip API.
