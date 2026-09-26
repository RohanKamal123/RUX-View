# RUX-View data schema and end-to-end operating procedure

> Source-based implementation document for the `main` branch. This describes the repository code and Alembic migrations as inspected; it is not a runtime validation report. The application schema is PostgreSQL with `pgvector`; the client also contains offline buffering implementations and the server uses short-lived Redis/in-memory state.

- Repository: `RohanKamal123/RUX-View`
- Branch inspected: `main`
- Primary document location: `docs/RUX_VIEW_DATA_SCHEMA_AND_PROCEDURE.md`
- Last source review: 2026-09-27

## 1. System at a glance

RUX-View is a CCTV intelligence service. Camera agents capture RTSP video and optional audio, reduce the stream locally to motion/audio triggers, and send authenticated triggers to the backend. The backend detects and tracks people/objects, builds incident sessions, asks configured AI services to interpret relevant frames or audio, performs person re-identification and cross-camera checks, decides whether an incident is actionable, stores the resulting record, and routes alerts such as Telegram, SMS, or voice notifications.

The repository has four materially different storage classes:

1. **PostgreSQL**: durable application data, including incidents, people, sightings, scene state, audio interpretation, camera configuration, tenants/users, API keys, usage, and payments.
2. **Client SQLite**: durable local offline queue in `connect/buffer/local_queue.py` (`visionos_queue.db` by default).
3. **Redis**: expiring/distributed runtime state such as tracking and rate-limit counters, with an in-memory fallback.
4. **Process/filesystem state**: active trigger sessions, query history, public-signup prototype records, clip-analysis metadata, temporary clip files, and a separate JSON-file trigger buffer.

Only the PostgreSQL objects are part of the Alembic relational schema. The other stores are included here because they receive or retain system data and affect operation.

## 2. PostgreSQL schema

### 2.1 Extensions, migrations, and conventions

- `alembic/versions/001_initial_schema.py` creates the initial 12-table schema and runs `CREATE EXTENSION IF NOT EXISTS vector`.
- Embeddings use `pgvector` `Vector(512)` in `persons.embedding` and `person_sightings.embedding`.
- `002_add_payments.py` adds `payments`.
- `003_add_telegram_fields.py` is idempotent and adds `users.telegram_chat_id` and `users.telegram_bot_token` if absent. Those fields are also present in the initial migration shown in the inspected branch, so this migration is a compatibility repair rather than a new logical table.
- Most IDs that identify a tenant, location, or camera are strings. Auto-incrementing integer IDs are used for event-like rows.
- The migrations define only three explicit foreign-key relationships: `person_sightings.event_id -> events.id`, `audio_events.event_id -> events.id`, and `api_key_usage.key_id -> api_keys.id`. Several `user_id`, `location_id`, and `camera_id` relationships are logical application relationships without database foreign-key constraints.
- Unique constraints: `(person_uid, user_id)`, `(camera_id, date, hour)` in `shop_analytics`, `(key_prefix, key_hash)` in `api_keys`, and `(key_id, timestamp)` in `api_key_usage`.
- Unless marked `server_default`, defaults in the migration are SQLAlchemy/application defaults. The authoritative deployed schema should therefore be checked against the actual database after migrations run.

### 2.2 Table-by-table definition

Notation: `PK` is a primary key, `FK` is a foreign key, `NN` is non-nullable, and `nullable` means the migration permits `NULL`. `JSON` values are structured Python/JSON payloads rather than a fixed nested schema.

#### `events` — incident/event records

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Durable event identifier. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `location_id` | varchar(36) | NN | Logical location. |
| `camera_id` | varchar(100) | NN | Source camera. |
| `incident_id` | varchar(100) | NN | Incident/session identifier used to group trigger activity. |
| `timestamp_start` | timestamptz | NN | Start of incident/event interval. |
| `timestamp_end` | timestamptz | nullable | End of interval when known. |
| `duration_sec` | float | nullable | Derived duration. |
| `threat_level` | varchar(10) | nullable | Normalized threat level. |
| `alert_sent` | boolean | default false | Whether alert delivery was recorded. |
| `alert_type` | varchar(30) | nullable | Alert channel/type. |
| `camera_mode` | varchar(20) | nullable | Camera operating mode. |
| `is_business_hours` | boolean | nullable | Business-hours classification. |
| `gemma_raw_json` | JSON | nullable | Raw first-stage/model output when used. |
| `gemini_decision` | JSON | nullable | Gemini/Vertex decision payload. |
| `timeline_json` | JSON | nullable | Timeline/incident details. |
| `thumbnail_url` | text | nullable | Reference to the stored/displayable event thumbnail. |
| `created_at` | timestamptz | server default `now()` | Persistence timestamp. |

#### `persons` — persistent person identities

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Row identifier. |
| `person_uid` | varchar(20) | NN | Application identity for a person. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `location_id` | varchar(36) | NN | Logical location scope. |
| `first_seen` | timestamptz | nullable | Earliest known sighting. |
| `last_seen` | timestamptz | nullable | Latest known sighting. |
| `sighting_count` | integer | default 0 | Number of recorded sightings. |
| `threat_flags` | integer | default 0 | Accumulated threat/behavior flags. |
| `is_staff` | boolean | default false | Tenant-provided staff classification. |
| `user_label` | varchar(100) | nullable | Human label for the identity. |
| `appearance_history` | JSON | nullable | Historical appearance attributes. |
| `embedding` | vector(512) | nullable | Re-identification embedding searched with pgvector. |
| `created_at` | timestamptz | server default `now()` | Row creation time. |

Constraint: `UNIQUE(person_uid, user_id)` named `uq_person_uid_user`.

#### `person_sightings` — per-observation person attributes

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Sighting row identifier. |
| `person_uid` | varchar(20) | NN | Matched or assigned person identity. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `event_id` | integer | nullable, FK to `events.id` | Event associated with the sighting. |
| `camera_id` | varchar(100) | nullable | Camera that observed the person. |
| `timestamp` | timestamptz | nullable | Observation time. |
| `clothing_top` | text | nullable | Upper-body clothing description. |
| `clothing_bottom` | text | nullable | Lower-body clothing description. |
| `clothing_colors` | text | nullable | Clothing color description. |
| `accessories` | text | nullable | Accessories description. |
| `hand_objects` | text | nullable | Objects held/carried. |
| `action` | text | nullable | Observed action. |
| `anomaly_signals` | text | nullable | Anomaly/behavior signals. |
| `embedding` | vector(512) | nullable | Sighting embedding for matching. |
| `thumbnail_url` | text | nullable | Sighting thumbnail reference. |

#### `scene_states` — structured scene snapshots

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Scene snapshot identifier. |
| `camera_id` | varchar(100) | NN | Source camera. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `timestamp` | timestamptz | NN | Scene observation time. |
| `gates_json` | JSON | nullable | Gates detected/interpreted in the scene. |
| `doors_json` | JSON | nullable | Doors detected/interpreted in the scene. |
| `vehicles_json` | JSON | nullable | Vehicles and attributes. |
| `lighting` | varchar(30) | nullable | Lighting classification. |
| `person_count` | integer | nullable | Count of people in the scene. |
| `raw_scene_json` | JSON | nullable | Raw scene-analysis payload. |

#### `audio_events` — audio classification and interpretation

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Audio record identifier. |
| `event_id` | integer | nullable, FK to `events.id` | Visual event correlated with the audio. |
| `camera_id` | varchar(100) | nullable | Source camera/audio agent. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `timestamp` | timestamptz | nullable | Audio trigger time. |
| `yamnet_class` | varchar(100) | nullable | YAMNet sound class. |
| `yamnet_confidence` | float | nullable | YAMNet confidence. |
| `whisper_transcript` | text | nullable | Optional Groq Whisper transcription. |
| `gemini_interpretation` | text | nullable | Gemini interpretation of the audio. |
| `threat_level` | varchar(10) | nullable | Audio-derived threat level. |
| `has_visual_match` | boolean | default false | Whether a related visual event was found. |
| `expires_at` | timestamptz | nullable | Retention/expiry metadata for audio. |

#### `shop_analytics` — hourly demographic aggregates

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Aggregate row identifier. |
| `camera_id` | varchar(100) | NN | Camera being aggregated. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `date` | date | NN | Local/reporting date. |
| `hour` | integer | NN | Hour bucket. |
| `customer_count` | integer | default/server default 0 | Total customers. |
| `male_count` | integer | default/server default 0 | Male classification count. |
| `female_count` | integer | default/server default 0 | Female classification count. |
| `unknown_gender` | integer | default/server default 0 | Unknown/undetermined gender count. |
| `age_teens` | integer | default/server default 0 | Teen age bucket. |
| `age_20s` | integer | default/server default 0 | 20s age bucket. |
| `age_30s` | integer | default/server default 0 | 30s age bucket. |
| `age_40s` | integer | default/server default 0 | 40s age bucket. |
| `age_50plus` | integer | default/server default 0 | 50+ age bucket. |
| `avg_dwell_seconds` | float | nullable | Average dwell time. |

Constraint: `UNIQUE(camera_id, date, hour)` named `uq_shop_analytics_camera_date_hour`.

#### `cameras` — camera configuration

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | varchar(100) | PK, NN | Camera identifier. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `location_id` | varchar(36) | NN | Logical location. |
| `name` | varchar(200) | nullable | Display name. |
| `mode` | varchar(20) | nullable | Camera mode. |
| `enabled` | boolean | default true | Whether processing is enabled. |
| `tier_required` | varchar(20) | nullable | Minimum subscription tier. |
| `gemma_cooldown_sec` | integer | default 15 | Per-camera first-stage/model cooldown. |
| `ignore_zones_json` | JSON | nullable | Regions excluded from processing. |
| `shop_hours_open` | time | nullable | Shop opening time. |
| `shop_hours_close` | time | nullable | Shop closing time. |
| `night_hours_start` | time | default `22:00` | Night window start. |
| `night_hours_end` | time | default `06:00` | Night window end. |
| `loiter_config_json` | JSON | nullable | Loitering policy/configuration. |
| `created_at` | timestamptz | server default `now()` | Creation time. |

#### `locations` — tenant locations

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | varchar(36) | PK, NN | Location identifier. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `name` | varchar(200) | nullable | Display name. |
| `type` | varchar(30) | nullable | Location type. |
| `camera_topology` | JSON | nullable | Camera relationships/layout. |
| `created_at` | timestamptz | server default `now()` | Creation time. |

#### `users` — tenant identity and notification/subscription data

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | varchar(36) | PK, NN | Internal tenant/user identifier. |
| `firebase_uid` | varchar(200) | nullable, unique | Firebase identity when used. |
| `email` | varchar(200) | nullable | Email address. |
| `phone` | varchar(20) | nullable | Phone number. |
| `telegram_chat_id` | varchar(50) | nullable | Telegram destination. |
| `telegram_bot_token` | varchar(200) | nullable | Per-user Telegram bot credential as modeled by the repository. Protect this value in deployment and logs. |
| `tier` | varchar(20) | default `free` | Subscription tier. |
| `trial_started_at` | timestamptz | nullable | Trial start. |
| `trial_ends_at` | timestamptz | nullable | Trial end. |
| `subscription_active` | boolean | default false | Subscription status. |
| `bkash_subscriber_id` | varchar(200) | nullable | bKash subscription reference. |
| `secondary_contact` | varchar(50) | nullable | Secondary notification contact. |
| `created_at` | timestamptz | server default `now()` | Creation time. |

#### `api_keys` — hashed API credentials

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | varchar(32) | PK, NN | API-key record identifier. |
| `user_id` | varchar(36) | NN | Owning tenant/user. |
| `name` | varchar(200) | NN | Human name. |
| `key_prefix` | varchar(8) | NN | Non-secret lookup/display prefix. |
| `key_hash` | varchar(64) | NN | Hash of the secret key; raw keys should not be persisted here. |
| `permissions` | JSON | NN, default `{}` | Permission claims. |
| `created_at` | timestamptz | server default `now()` | Creation time. |
| `expires_at` | timestamptz | nullable | Expiry time. |
| `last_used_at` | timestamptz | nullable | Last successful/recorded use. |
| `is_active` | boolean | default true | Revocation/activation flag. |

Constraint: `UNIQUE(key_prefix, key_hash)` named `uq_api_key_prefix_hash`.

#### `api_key_usage` — per-request API-key audit data

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Usage row identifier. |
| `key_id` | varchar(32) | NN, FK to `api_keys.id` | Key used. |
| `user_id` | varchar(36) | NN | Tenant/user associated with request. |
| `timestamp` | timestamptz | NN | Request time. |
| `endpoint` | varchar(200) | NN | Requested endpoint. |
| `response_code` | integer | NN | HTTP result code. |
| `response_time_ms` | float | nullable | Request duration. |
| `error_message` | text | nullable | Error detail when applicable. |

Constraint: `UNIQUE(key_id, timestamp)` named `uq_key_timestamp`.

#### `payments` — manual/payment-provider transaction records

Created by migration `002_add_payments.py`; it is not present in the initial migration's downgrade list because it is a later revision.

| Column | Type | Null/default | Meaning |
|---|---|---|---|
| `id` | integer | PK, auto-increment, NN | Payment row identifier. |
| `user_id` | varchar(200) | NN | User/tenant reference. |
| `tier` | varchar(20) | NN | Purchased tier. |
| `amount_bdt` | integer | NN | Amount in Bangladeshi taka. |
| `transaction_id` | varchar(100) | NN | Provider transaction reference. |
| `payment_method` | varchar(20) | server default `bkash` | Payment method, with bKash as default. |
| `status` | varchar(20) | server default `pending` | Payment state. |
| `notes` | text | nullable | Operator/provider notes. |
| `created_at` | timestamptz | server default `now()` | Creation time. |
| `verified_at` | timestamptz | nullable | Verification time. |

There is no explicit foreign key from `payments.user_id` to `users.id` in the migration.

## 3. Non-PostgreSQL storage and runtime state

### 3.1 Client SQLite: `trigger_queue`

`connect/buffer/local_queue.py` defines a SQLite database, default filename `visionos_queue.db`, with this schema:

```sql
CREATE TABLE IF NOT EXISTS trigger_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,  -- ISO 8601 timestamp
    trigger_data TEXT    NOT NULL   -- JSON-encoded trigger payload
);
```

The JSON in `trigger_data` can contain frame or audio trigger data, including camera ID, type, timestamp, encoded media or payload data, and any fields needed for resend. The queue is thread-locked, FIFO by `id`, defaults to a 48-hour TTL, defaults to a 500-event maximum, deletes expired rows, and drops the oldest rows when full. It is flushed when connectivity returns; failed sends are re-enqueued.

### 3.2 Client JSON-file `LocalBuffer`

`connect/transport/trigger_sender.py` contains a separate `LocalBuffer` implementation using a directory (default `buffer/`) rather than SQLite. Each buffered trigger is a JSON file named with a UUID. The implementation adds `_buffered_at` and `_buffer_id`; normal payload fields include `type`, `camera_id`, `data`, and `timestamp`. Files are sorted, sent, and deleted on successful flush; failures are re-buffered. This is a second offline-buffer path, not a PostgreSQL table.

### 3.3 Redis and in-memory cache state

The cache manager uses Redis when available and falls back to an in-memory LRU cache. Generic cache entries contain a caller-provided key, serialized value, TTL, and local cache metadata. The rate limiter uses keys of the form `ratelimit:{key}`, increments them, sets a window expiry, and reads the counter/TTL. The tracking path uses camera-scoped Redis state such as `track:{camera_id}` for BoT-SORT/active-track continuity. These keys are operational state, not durable relational records; exact payload shapes are owned by the calling subsystem and can expire or be lost during Redis failure/restart.

### 3.4 Process memory and temporary files

The inspected server/client code also keeps the following outside PostgreSQL:

- Active trigger/incident sessions used to merge nearby frame triggers.
- In-memory natural-language query history.
- An in-memory public-signup/reset prototype store.
- In-memory clip-analysis metadata (`clip_id`, temporary source path, frame count, FPS, duration, status, progress, and error state). Uploaded clip bytes are written to a temporary `source.mp4` under a temp `clip_analysis` directory.
- Transient model/tracking/cache objects and pipeline state.

These stores do not survive process restart unless the underlying code explicitly writes them to a file or database.

## 4. All data entering, moving through, or produced by the system

### 4.1 Identity, tenancy, and configuration data

- Firebase UID, internal user ID, email, phone, subscription tier/trial state, bKash subscriber reference, and secondary contact.
- Telegram chat ID and bot token used for notification routing; bot tokens are credentials and must be treated as secrets even though the current schema models them as user data.
- API-key names, prefixes, hashes, permissions, active/expiry state, and request audit metadata.
- Location names/types and camera topology.
- Camera name, mode, enabled state, required tier, AI cooldown, ignore zones, shop hours, night hours, and loitering configuration.
- Runtime configuration such as model thresholds, trigger confidence, retention, alert routing, rate limits, and service endpoints.

### 4.2 Video and image data

- RTSP video frames captured by the client.
- Motion-derived frame triggers, camera ID, location ID, user/auth context, timestamps, mode, confidence, and optional camera profile.
- JPEG bytes/base64 image payloads sent to `POST /api/triggers/frame`.
- YOLOv8 ONNX detections, bounding boxes/classes/confidences, motion-gate results, and BoT-SORT track IDs/state.
- AI inputs: selected frames, incident context, scene context, and cross-camera/repeat/ghost context.
- AI outputs: raw model JSON, normalized threat/incident decisions, timeline data, scene objects, person attributes, anomaly signals, and thumbnails/thumbnail URLs.
- Uploaded video clips for analysis, temporary encoded video bytes, sampled frames, FPS, duration, progress, errors, and streamed analysis status.

### 4.3 Person and scene data

- Persistent person UID, first/last seen, count, threat flags, staff flag, human label, appearance history, and 512-dimensional embedding.
- Sighting-level clothing, colors, accessories, carried objects, action, anomaly signals, timestamp, camera, thumbnail, and embedding.
- Scene gates, doors, vehicles, lighting, person count, and raw scene JSON.
- Shop analytics aggregates: hourly customer count, gender buckets, age buckets, and average dwell seconds.

### 4.4 Audio data

- Audio captured by the client and encoded into audio trigger payloads sent to `POST /api/triggers/audio`.
- YAMNet sound class and confidence.
- Optional Groq Whisper transcript.
- Gemini audio interpretation, normalized threat level, visual-match flag, event association, and expiry metadata.

### 4.5 Alerts and external-service payloads

The alert router can construct Telegram, SMS, and voice notification payloads from event/incident data. Those payloads can include threat level, camera/location context, timestamps, timeline/decision text, and thumbnail/media references. Provider responses and delivery outcomes feed back into `events.alert_sent`/`events.alert_type` and operational logs. Provider credentials and API keys are configuration secrets, not business records to expose in this document.

## 5. Complete end-to-end operating procedure

### Phase 0 — Provision and configure

1. Provide PostgreSQL connectivity and enable the `pgvector` extension through Alembic revision `001`.
2. Run the Alembic chain in order: `001` initial schema, `002` payments, then `003` Telegram compatibility fields.
3. Configure the backend environment and services: database, Firebase/auth context, AI providers, Redis/Upstash when used, alert providers, and application secrets. Do not put raw credentials in code, trigger payloads, or logs.
4. Seed or create the tenant, locations, cameras, and notification settings. Camera mode and tier gates determine which processing paths are permitted.
5. Start the backend dashboard/server. It wires the trigger router, storage layer, pipeline manager, analytics router, clip-analysis router, and clip-test router. If the AI pipeline is unavailable, the server warns that triggers may be stored only.

### Phase 1 — Start a camera agent

1. The connect client loads configuration and starts its camera/audio modules, transport sender, retry logic, and local buffering.
2. It opens an RTSP source through OpenCV, reads frames, and applies local motion detection. The client does not send every frame by default; it sends motion-qualified frame triggers.
3. When audio is enabled, the client captures audio and runs YAMNet classification. Sound class/confidence can be attached to an audio trigger; the backend may perform further transcription and interpretation.
4. If the network is unavailable, the client stores triggers in the active local buffer implementation. When connectivity returns, it sends them FIFO and retains failed items for another attempt.

### Phase 2 — Authenticate and ingest a trigger

1. The agent sends a frame trigger to `POST /api/triggers/frame` or an audio trigger to `POST /api/triggers/audio`.
2. The request carries the camera identifier, encoded image/audio when applicable, timestamp, mode, confidence, location fallback/context, and optional camera profile/YAMNet result. Authentication is checked before tenant-scoped processing.
3. The trigger API normalizes missing timestamps, resolves location context, applies runtime configuration, and passes the trigger to the pipeline manager when it is wired. A backend running without the pipeline can record/store the trigger path without completing AI analysis.
4. `GET /api/triggers/recent` reads recent frame/audio events for the authenticated user, and `GET /api/triggers/image/{event_id}` serves an event image where available.

### Phase 3 — Gate, track, and build an incident session

1. For visual triggers, the detection gate uses the YOLOv8 ONNX detector to decide whether relevant objects/persons are present and to produce detections.
2. BoT-SORT maintains track continuity. Redis-backed camera track state can allow continuity across worker calls; the cache manager falls back to local memory when Redis is not usable.
3. The incident builder groups related triggers and throttles expensive AI calls. The live constant/configuration path uses a 60-second Gemini interval; comments/docstrings still describe 120 seconds. Treat 60 seconds as the implemented default unless deployment configuration overrides it.
4. Trigger sessions are cleaned up after `SESSION_TIMEOUT_SEC = 180`. The frame route description says frames within 45 seconds are merged, but the cleanup constant is 180 seconds; these are not equivalent and should be reconciled before using either as a product guarantee.
5. The builder retains enough context to compare tracks, avoid duplicate calls, and produce a candidate incident rather than treating each motion frame as a separate alert.

### Phase 4 — Analyze visual and audio context

1. Selected visual frames and context go to the configured Gemini/Vertex AI analysis path. The event schema preserves raw model JSON, the normalized decision, and a timeline JSON payload.
2. Person crops/attributes can be embedded into 512-dimensional vectors. The Re-ID engine searches existing `persons`/`person_sightings` vectors with pgvector and updates or creates a person identity within the tenant/location scope.
3. Cross-camera, repeat-sighting, ghost/false-positive, business-hours, night-hours, ignore-zone, loitering, staff, and tier/policy checks contribute to the final decision.
4. For audio, YAMNet classifies the sound; optional Groq Whisper produces a transcript; Gemini interprets the transcript/classification. The audio-correlation path looks for a matching visual event. Audio-only incidents remain possible and are stored with `audio_events.event_id` null when no visual match exists.
5. Scene interpretation can produce gate/door/vehicle/lighting/person-count data and a raw scene JSON snapshot for `scene_states`.

### Phase 5 — Decide, persist, and correlate

1. The incident decision determines whether the candidate is a threat/actionable event, its normalized threat level, alert type, time interval, and timeline.
2. Create or update `events`; associate the logical user, location, camera, and incident ID. Persist model outputs and thumbnail references as available.
3. Persist person identity and sighting rows, scene snapshots, and audio rows as applicable. Audio records may carry `expires_at` for retention handling.
4. Update `alert_sent` and `alert_type` after alert routing attempts according to the alert implementation.
5. For shop/analytics paths, aggregate camera activity into the hourly `shop_analytics` uniqueness bucket. The schema is present even though the current analytics API surface is not a complete production reporting implementation.

### Phase 6 — Route alerts

1. The alert router selects configured Telegram, SMS, and/or voice channels based on the user/camera policy and incident severity.
2. Build the notification from the persisted decision, camera/location context, timestamp/timeline, and thumbnail/media reference.
3. Send through the configured provider, record delivery outcome, and avoid repeatedly alerting the same incident when the incident/session logic marks it as already handled.
4. If a provider fails, retain the event decision and delivery state separately; a delivery failure should not erase the underlying incident evidence.

### Phase 7 — Operate the APIs and dashboard

- **Cameras/locations/users**: CRUD/configuration routes manage tenant-scoped camera and location metadata and user notification/subscription fields.
- **Payments**: payment routes create and list bKash/Nagad-style transaction records; verification/status fields are stored in `payments`.
- **Triggers/events**: ingest, recent-event retrieval, and image retrieval are implemented around the trigger/event path.
- **Natural-language queries**: `POST /api/queries/natural` and `GET /api/queries/history` expose the query surface. The query engine has production-shaped flow, but `_fetch_matching_events()` currently returns mock empty data, so results should not be described as a complete event search until that method is implemented.
- **Analytics**: analytics routes exist, but the inspected implementation explicitly contains placeholder behavior. Do not treat them as a complete reporting API solely because `shop_analytics` exists.
- **Clips**: clip upload/run/status code stores clip metadata in memory and temporary files and streams progress; separate clip routes/analytics surfaces contain placeholders where noted in source. A restart can lose in-memory clip metadata and make the temporary clip unavailable.
- **Public signup/reset**: the public signup/reset implementation is an in-memory prototype. It does not create Firebase accounts, persist users, or send email in the inspected code.

## 6. Retention, failure, and restart behavior

- PostgreSQL rows are durable subject to database backup/retention policy. Audio rows carry an explicit expiry field, but the presence of `expires_at` alone is not proof that a deletion worker is active.
- Client SQLite queues survive client process restarts, clean expired records, and cap capacity at 500 by default.
- JSON-file buffering survives a client process restart as long as its buffer directory remains available.
- Redis tracking/cache/rate-limit state is disposable. Loss of Redis can reduce continuity and distributed coordination; cache manager and rate limiter have in-memory fallback behavior.
- Active incident sessions, query history, public signup records, and clip metadata are process-local unless a separate persistence path is added. Restarting the relevant process can lose them.
- Temporary uploaded clips are filesystem artifacts, not PostgreSQL objects. They need explicit cleanup and storage policy for production use.
- The repository contains legacy storage comments/docstrings that mention MEGA.nz, while current server wiring uses PostgreSQL-oriented `HybridCRUD`. The PostgreSQL path and actual server wiring should be treated as authoritative unless deployment code proves otherwise.

## 7. Security and privacy handling

- Treat camera images, audio, transcripts, embeddings, person attributes, phone/email data, notification destinations, and payment references as sensitive tenant data.
- Keep API-key secrets out of database rows; the schema is designed to store a prefix and hash. Rotate/revoke keys through `is_active`/expiry rather than logging or reusing raw values.
- Protect Firebase credentials, provider API keys, Telegram bot tokens, database URLs, Redis URLs, and AI credentials through deployment secrets. Do not copy them into this document or into trigger JSON.
- Enforce tenant scoping on every read/write: `user_id` is present throughout the core tables, but many relations are logical rather than database-enforced.
- Define explicit retention/deletion policies for thumbnails, temporary clips, raw audio, transcripts, embeddings, and event JSON. Current code exposes retention metadata but does not make every lifecycle operation durable or automatic.

## 8. Implementation gaps and discrepancies to resolve

1. Reconcile the 180-second implemented trigger session timeout with the 45-second route description.
2. Reconcile the 60-second implemented Gemini interval with the 120-second comments/docstrings and configuration documentation.
3. Implement real event retrieval in `backend/ai/query_engine.py` (`_fetch_matching_events()` currently returns mock empty data) before presenting natural-language search as complete.
4. Replace or clearly label placeholder analytics and clip APIs; connect analytics reporting to `shop_analytics` if that is the intended product behavior.
5. Replace the in-memory public signup/reset prototype with durable user creation, Firebase integration, email/reset delivery, and abuse controls before production use.
6. Choose one offline buffer as the supported path or document the selection rule between SQLite `LocalQueue` and JSON-file `LocalBuffer`.
7. Add or verify database foreign keys for tenant/location/camera relationships if referential integrity is required.
8. Add an explicit retention worker/job for `audio_events.expires_at`, temporary clip files, thumbnails, and other raw media if policy requires deletion.
9. Remove or update legacy MEGA.nz storage documentation so operators do not follow a path that the current `HybridCRUD` wiring does not use.
10. Run migrations and integration tests against a real PostgreSQL/pgvector, Redis, AI-provider-mock, alert-provider-mock, and offline-client environment; this document does not claim those tests have been run.

## 9. Source map

The findings above were derived from the following repository areas:

- `alembic/versions/001_initial_schema.py`, `002_add_payments.py`, `003_add_telegram_fields.py` — PostgreSQL schema and migration history.
- `backend/storage/database.py`, `engine.py`, `crud.py`, `pg_crud.py`, `hybrid_crud.py` — storage abstraction, PostgreSQL access, and server wiring behavior.
- `connect/main.py`, `connect/transport/trigger_sender.py`, `connect/buffer/local_queue.py` — client capture, transport, retry, SQLite queue, and JSON-file buffering.
- `backend/api/triggers.py` — frame/audio ingestion, session cleanup, recent events, and image routes.
- `backend/core/pipeline.py`, `pipeline_v2.py`, `detection/*`, `incident_tracker.py`, `detection/incident_builder.py` — detection, tracking, incident grouping, and pipeline orchestration.
- `backend/ai/ai_client.py`, `reid_engine.py`, `query_engine.py` — AI calls, embeddings/re-identification, and query behavior.
- `backend/core/audio_correlation.py`, `audio_only_incident.py` — audio/visual correlation and audio-only incident paths.
- `backend/alerts/alert_router.py` — notification routing.
- `backend/api/analytics.py`, `clips.py`, `clip_analysis.py`, `queries.py`, `backend/dashboard/server.py` — operational APIs, placeholders, and application wiring.
- `backend/core/cache_manager.py` — Redis/in-memory cache and rate-limit state.

This document intentionally distinguishes source-defined schema and code paths from behavior that still requires deployment configuration or runtime verification.
