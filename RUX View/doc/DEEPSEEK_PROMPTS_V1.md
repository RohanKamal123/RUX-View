# Vision OS — DeepSeek Coding Prompts
# Copy-paste these prompts into DeepSeek to generate each sprint's code
# Each prompt includes: context + function signatures + test cases

---

## How to Use

1. Open DeepSeek (chat.deepseek.com)
2. Copy the entire prompt block for the sprint you want
3. Paste into DeepSeek
4. DeepSeek will generate: code + tests + docstring
5. Save the generated files to the correct paths
6. Run `pytest` to verify tests pass
7. Commit with `git commit -m "feat: [module] what it does"`

---

## SPRINT 1.2 — Database Schema
### File: backend/storage/database.py
### Tests: backend/tests/unit/test_database.py

```
You are building the database layer for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: SQLAlchemy 2.0 async + psycopg2-binary + pgvector
- Database: Cloud SQL Postgres 15 with pgvector extension
- All DB calls must be async (await)
- 9 tables: events, persons, person_sightings, scene_states, audio_events, shop_analytics, cameras, locations, users

PERSONS TABLE (with pgvector):
```sql
CREATE TABLE persons (
  id                  SERIAL PRIMARY KEY,
  person_uid          VARCHAR(20) NOT NULL,
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  first_seen          TIMESTAMPTZ,
  last_seen           TIMESTAMPTZ,
  sighting_count      INTEGER DEFAULT 0,
  threat_flags        INTEGER DEFAULT 0,
  is_staff            BOOLEAN DEFAULT FALSE,
  user_label          VARCHAR(100),
  appearance_history  JSONB,
  embedding           vector(512),
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(person_uid, user_id)
);
CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops);
```

EVENTS TABLE:
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
  threat_level        VARCHAR(10),
  alert_sent          BOOLEAN DEFAULT FALSE,
  alert_type          VARCHAR(30),
  camera_mode         VARCHAR(20),
  is_business_hours   BOOLEAN,
  gemma_raw_json      JSONB,
  gemini_decision     JSONB,
  timeline_json       JSONB,
  thumbnail_url       TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_events_user_time ON events(user_id, timestamp_start DESC);
CREATE INDEX idx_events_camera ON events(camera_id, timestamp_start DESC);
CREATE INDEX idx_events_threat ON events(user_id, threat_level, timestamp_start DESC);
```

PERSON_SIGHTINGS TABLE:
```sql
CREATE TABLE person_sightings (
  id                  SERIAL PRIMARY KEY,
  person_uid          VARCHAR(20) NOT NULL,
  user_id             UUID NOT NULL,
  event_id            INTEGER REFERENCES events(id),
  camera_id           VARCHAR(100),
  timestamp           TIMESTAMPTZ,
  clothing_top        TEXT,
  clothing_bottom     TEXT,
  clothing_colors     TEXT,
  accessories         TEXT,
  hand_objects        TEXT,
  action              TEXT,
  anomaly_signals     TEXT,
  embedding           vector(512),
  thumbnail_url       TEXT
);
CREATE INDEX idx_sightings_person ON person_sightings(person_uid, user_id, timestamp DESC);
```

SCENE_STATES TABLE:
```sql
CREATE TABLE scene_states (
  id                  SERIAL PRIMARY KEY,
  camera_id           VARCHAR(100) NOT NULL,
  user_id             UUID NOT NULL,
  timestamp           TIMESTAMPTZ NOT NULL,
  gates_json          JSONB,
  doors_json          JSONB,
  vehicles_json       JSONB,
  lighting            VARCHAR(30),
  person_count        INTEGER,
  raw_scene_json      JSONB
);
CREATE INDEX idx_scene_camera_time ON scene_states(camera_id, timestamp DESC);
```

AUDIO_EVENTS TABLE:
```sql
CREATE TABLE audio_events (
  id                  SERIAL PRIMARY KEY,
  event_id            INTEGER REFERENCES events(id),
  camera_id           VARCHAR(100),
  user_id             UUID NOT NULL,
  timestamp           TIMESTAMPTZ,
  yamnet_class        VARCHAR(100),
  yamnet_confidence   FLOAT,
  whisper_transcript  TEXT,
  gemini_interpretation TEXT,
  threat_level        VARCHAR(10),
  has_visual_match    BOOLEAN DEFAULT FALSE,
  expires_at          TIMESTAMPTZ
);
```

SHOP_ANALYTICS TABLE:
```sql
CREATE TABLE shop_analytics (
  id                  SERIAL PRIMARY KEY,
  camera_id           VARCHAR(100),
  user_id             UUID NOT NULL,
  date                DATE NOT NULL,
  hour                INTEGER,
  customer_count      INTEGER DEFAULT 0,
  male_count          INTEGER DEFAULT 0,
  female_count        INTEGER DEFAULT 0,
  unknown_gender      INTEGER DEFAULT 0,
  age_teens           INTEGER DEFAULT 0,
  age_20s             INTEGER DEFAULT 0,
  age_30s             INTEGER DEFAULT 0,
  age_40s             INTEGER DEFAULT 0,
  age_50plus          INTEGER DEFAULT 0,
  avg_dwell_seconds   FLOAT,
  UNIQUE(camera_id, date, hour)
);
```

CAMERAS TABLE:
```sql
CREATE TABLE cameras (
  id                  VARCHAR(100) PRIMARY KEY,
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  name                VARCHAR(200),
  mode                VARCHAR(20),
  enabled             BOOLEAN DEFAULT TRUE,
  tier_required       VARCHAR(20),
  gemma_cooldown_sec  INTEGER DEFAULT 15,
  ignore_zones_json   JSONB,
  shop_hours_open     TIME,
  shop_hours_close    TIME,
  night_hours_start   TIME DEFAULT '22:00',
  night_hours_end     TIME DEFAULT '06:00',
  loiter_config_json  JSONB,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

LOCATIONS TABLE:
```sql
CREATE TABLE locations (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL,
  name                VARCHAR(200),
  type                VARCHAR(30),
  camera_topology     JSONB,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

USERS TABLE:
```sql
CREATE TABLE users (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  firebase_uid        VARCHAR(200) UNIQUE,
  email               VARCHAR(200),
  phone               VARCHAR(20),
  telegram_chat_id    VARCHAR(50),
  telegram_bot_token  VARCHAR(200),
  tier                VARCHAR(20) DEFAULT 'free',
  trial_started_at    TIMESTAMPTZ,
  trial_ends_at       TIMESTAMPTZ,
  subscription_active BOOLEAN DEFAULT FALSE,
  bkash_subscriber_id VARCHAR(200),
  secondary_contact   VARCHAR(50),
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

REQUIREMENTS:
1. Use SQLAlchemy 2.0 async with async_sessionmaker
2. Use asyncpg driver (postgresql+asyncpg://)
3. All CRUD operations must be async functions
4. Include get_db() async generator for FastAPI dependency injection
5. Include pgvector support for persons.embedding column
6. Include Alembic migration setup
7. Max 200 lines per file (split if needed)

FUNCTIONS TO IMPLEMENT:
```python
# Connection
async def get_db() -> AsyncGenerator[AsyncSession, None]
async def init_db() -> None  # Create all tables

# Events CRUD
async def create_event(db: AsyncSession, event_data: dict) -> Event
async def get_event(db: AsyncSession, event_id: int) -> Event | None
async def get_events(db: AsyncSession, user_id: str, filters: dict) -> list[Event]
async def update_event(db: AsyncSession, event_id: int, updates: dict) -> Event

# Persons CRUD (with pgvector)
async def create_person(db: AsyncSession, person_data: dict) -> Person
async def get_person(db: AsyncSession, person_uid: str, user_id: str) -> Person | None
async def find_similar_persons(db: AsyncSession, embedding: list, location_id: str, limit: int = 5) -> list[dict]
async def update_person_sighting(db: AsyncSession, person_uid: str, user_id: str) -> None

# Person Sightings
async def create_sighting(db: AsyncSession, sighting_data: dict) -> PersonSighting
async def get_person_sightings(db: AsyncSession, person_uid: str, user_id: str) -> list[PersonSighting]

# Scene States
async def save_scene_state(db: AsyncSession, state_data: dict) -> SceneState
async def get_latest_scene_state(db: AsyncSession, camera_id: str) -> SceneState | None

# Audio Events
async def create_audio_event(db: AsyncSession, audio_data: dict) -> AudioEvent
async def get_expired_transcripts(db: AsyncSession) -> list[AudioEvent]
async def delete_audio_event(db: AsyncSession, event_id: int) -> None

# Shop Analytics
async def upsert_shop_analytics(db: AsyncSession, analytics_data: dict) -> ShopAnalytic
async def get_shop_analytics(db: AsyncSession, camera_id: str, date: date) -> list[ShopAnalytic]

# Cameras
async def create_camera(db: AsyncSession, camera_data: dict) -> Camera
async def get_user_cameras(db: AsyncSession, user_id: str) -> list[Camera]
async def update_camera(db: AsyncSession, camera_id: str, updates: dict) -> Camera
async def delete_camera(db: AsyncSession, camera_id: str) -> None

# Locations
async def create_location(db: AsyncSession, location_data: dict) -> Location
async def get_user_locations(db: AsyncSession, user_id: str) -> list[Location]

# Users
async def get_or_create_user(db: AsyncSession, firebase_uid: str, email: str) -> User
async def update_user_tier(db: AsyncSession, user_id: str, tier: str) -> User
async def get_user_by_firebase_uid(db: AsyncSession, firebase_uid: str) -> User | None
```

TEST CASES TO WRITE (test_database.py):
```python
test_create_all_tables()
test_insert_event()
test_insert_person()
test_insert_person_with_embedding()
test_pgvector_similarity_query()
test_insert_scene_state()
test_insert_shop_analytics()
test_user_tier_query()
```

OUTPUT: Generate the complete database.py file with all SQLAlchemy models, async CRUD functions, and the test file. Use proper type hints and docstrings.
```

---

## SPRINT 1.3 — Firebase Auth Middleware
### File: backend/dashboard/auth.py
### Tests: backend/tests/unit/test_auth.py

```
You are building the authentication middleware for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: Firebase Admin SDK + FastAPI
- Auth: Firebase ID tokens verified server-side
- Tiers: free, household, business
- All routes protected with get_current_user() dependency
- Premium routes use require_tier() decorator

KEY DECISIONS:
- D012: Firebase Auth (NOT custom auth) — Google ecosystem, free tier
- Firebase Admin SDK initialised once at startup

FUNCTIONS TO IMPLEMENT:
```python
import firebase_admin
from firebase_admin import auth as firebase_auth
from fastapi import Header, HTTPException, Depends
from functools import wraps

# Initialise Firebase Admin SDK
def init_firebase() -> None:
    """Initialise Firebase Admin SDK from service account JSON."""

# Verify Firebase ID token
async def verify_token(token: str) -> dict | None:
    """Verify Firebase ID token.
    Returns: {uid, email, tier, subscription_active} or None
    Raises: HTTPException 401 if invalid
    """

# FastAPI dependency for protected routes
async def get_current_user(authorization: str = Header(None)) -> dict:
    """Extract Bearer token from Authorization header.
    Returns: user dict from verify_token()
    Raises: HTTPException 401 if missing/invalid
    """

# Tier check decorator
def require_tier(required_tier: str):
    """Decorator for routes requiring specific tier.
    Tier hierarchy: free < household < business
    Raises: HTTPException 403 if insufficient tier
    """
```

TEST CASES TO WRITE (test_auth.py):
```python
test_valid_token_passes()
test_invalid_token_rejected()
test_tier_check_household()
test_tier_check_business()
test_free_tier_blocked_premium_route()
```

OUTPUT: Generate auth.py with all functions, proper error handling, and test file. Use async functions where appropriate.
```

---

## SPRINT 1.4 — AI Client (Gemini 2.0 Flash + Groq)
### File: backend/ai/ai_client.py + backend/ai/groq_client.py
### Tests: backend/tests/unit/test_ai_client.py

```
You are building the AI client for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: google-generativeai (Gemini 2.0 Flash) + groq (Whisper-compatible API)
- Single ai_client.py for ALL Gemini operations (NOT split into gemma_client.py + gemini_client.py)
- All functions async
- Gemini 2.0 Flash handles both vision analysis AND reasoning/decisions
- Groq handles Bangla audio transcription via whisper-large-v3-turbo

KEY DECISIONS:
- D001: Gemini 2.0 Flash unified (NOT split Gemma/Gemini)
- D003: Groq Whisper-compatible API for Bangla transcription (replaced OpenAI Whisper)
- D026: All calls async (await)

GEMINI SETUP:
```python
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp')
```

GROQ SETUP:
```python
from groq import AsyncGroq
client = AsyncGroq(api_key=GROQ_API_KEY)
```

LIVE VISION PROMPT (fast — used during incidents):
```
Analyse this CCTV frame quickly. Return JSON only.
No explanation. No markdown.

{
  "persons": [{
    "gender": "male/female/unknown",
    "age_estimate": 28,
    "clothing": "red shirt, black jeans",
    "hand_objects": ["phone"],
    "carried_items": ["backpack"],
    "action": "walking/running/standing/crouching/climbing",
    "anomaly_signals": [],
    "bbox_normalized": [0.2, 0.1, 0.45, 0.9]
  }],
  "person_count": 1,
  "scene_alerts": [],
  "vehicles": [],
  "gates_visible": {}
}
```

QUERY PROMPT (detailed — for NL queries):
```
Analyse this CCTV frame in extreme detail.
This data answers user queries like
"who wore red?" or "what was in their hand?"
Be obsessively descriptive. Return JSON only.

{
  "persons": [{
    "gender": "male/female/unknown",
    "age_estimate": 28,
    "clothing": {
      "top": "exact color and garment type",
      "bottom": "exact color and type",
      "shoes": "description or unknown",
      "accessories": ["cap", "watch", "glasses"]
    },
    "hand_objects": ["mobile phone", "keys"],
    "carried_items": ["black backpack"],
    "action": "detailed action description",
    "body_language": "relaxed/nervous/aggressive/hurried",
    "face_direction": "looking at camera/away/down",
    "position": "description relative to doors/gates/objects",
    "bbox_normalized": [0.2, 0.1, 0.45, 0.9]
  }],
  "scene": {
    "gates": {"gate_1": "open/closed/unknown"},
    "doors": {"front_door": "open/closed/unknown"},
    "vehicles": ["white sedan parked left"],
    "unattended_objects": ["black bag near gate"],
    "lighting": "daylight/night/artificial/IR",
    "weather_hint": "sunny/overcast/rainy/dark"
  },
  "anomalies": []
}
```

INCIDENT DECISION PROMPT:
```
You are a CCTV security analyst for a property in Bangladesh.

Camera: {camera_name}
Mode: {camera_mode}
Time: {timestamp}
Location type: {location_type}
Business hours: {is_business_hours}

Incident timeline (vision observations):
{timeline}

Duration: {duration}s
Re-ID result: {reid_result}
Known person: {is_known} ({label})
Audio context: {audio_context}
Recent history (last 10 events this camera): {history}

Return JSON only:
{
  "threat_level": "LOW/MEDIUM/HIGH",
  "alert_message": "one sentence, plain text, no markdown",
  "action": "LOG_ONLY/TELEGRAM_TEXT/TELEGRAM_PHOTO/EMERGENCY",
  "reasoning": "brief explanation",
  "person_ids": ["PERSON_007"],
  "follow_up": "any recommended action for owner"
}
```

FUNCTIONS TO IMPLEMENT (ai_client.py):
```python
# Vision Analysis (fast — used during incidents)
async def analyse_frame(jpeg_bytes: bytes) -> dict
    # Returns: {persons: [{gender, age_estimate, clothing, hand_objects, carried_items, action, bbox_normalized}], person_count, scene_alerts, vehicles}

# Vision Analysis (detailed — for NL queries)
async def analyse_frame_detailed(jpeg_bytes: bytes) -> dict
    # Returns: exhaustive clothing/accessories/position data

# Shop Entry Analysis
async def analyse_shop_entry(jpeg_bytes: bytes) -> dict
    # Returns: {gender, age_group, carried_items, group_size, confidence}

# Incident Decision
async def make_incident_decision(timeline: list, context: dict) -> dict
    # Returns: {threat_level, alert_message, action, reasoning, person_ids, follow_up}

# Query Answering
async def answer_query(question: str, events: list, analyses: list) -> str
    # Returns: plain text answer with person IDs and timestamps

# Scene State Query
async def answer_scene_state(question: str, world_state: dict) -> str
    # Returns: answer about gate/door status

# Daily/Weekly Digest
async def generate_daily_digest(events: dict, tier: str) -> str
async def generate_weekly_digest(events: dict, tier: str) -> str
    # Returns: Telegram-ready text (max 200 words for free tier)

# Re-ID Tiebreaker (uncertainty zone 0.5-0.72)
async def reid_tiebreaker(desc_a: str, desc_b: str, time_gap: int) -> dict
    # Returns: {same_person: bool, confidence: float, reasoning: str}
```

FUNCTIONS TO IMPLEMENT (groq_client.py):
```python
async def transcribe_audio(audio_bytes: bytes) -> str
    # Uses Groq Whisper-compatible API (whisper-large-v3-turbo)
    # Returns: Bangla transcript text
```

TEST CASES TO WRITE (test_ai_client.py):
```python
test_analyse_frame_returns_required_fields()
test_analyse_frame_detailed_prompt_parse()
test_shop_entry_returns_demographics()
test_incident_decision_parse()
test_query_answer_format()
test_digest_under_200_words_free_tier()
test_reid_tiebreaker_returns_match_bool()
test_groq_transcription()
test_invalid_response_handled_gracefully()
```

OUTPUT: Generate ai_client.py and groq_client.py with all functions, proper error handling, JSON parsing with fallbacks, and test file. Use async/await throughout.
```


---

## SPRINT 1.5 — API Stubs
### Files: backend/api/triggers.py, cameras.py, users.py, queries.py
### Tests: backend/tests/unit/test_api.py

```
You are building the API stubs for Vision OS, an AI-powered CCTV intelligence SaaS platform for Bangladesh.

CONTEXT:
- Stack: FastAPI + async
- All routes protected with get_current_user() dependency from backend/dashboard/auth.py
- Premium routes use require_tier() decorator
- Stubs return placeholder responses with correct status codes
- Real logic will be added in Phase 3

KEY DECISIONS:
- D005: Trigger-only (not continuous streaming)


ENDPOINTS TO STUB:

triggers.py:
```python
from fastapi import APIRouter, Depends, UploadFile, File, Form
from backend.dashboard.auth import get_current_user

router = APIRouter(prefix="/triggers", tags=["triggers"])

@router.post("/frame")
async def receive_frame_trigger(
    jpeg: UploadFile = File(...),
    motion_result: str = Form(...),
    camera_id: str = Form(...),
    timestamp: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Receive JPEG trigger from Vision OS Connect client.
    Returns: {status: "received", incident_id: str}
    """
    # TODO: Sprint 3.6 — call pipeline.process_trigger()

@router.post("/audio")
async def receive_audio_trigger(
    audio: UploadFile = File(...),
    yamnet_result: str = Form(...),
    camera_id: str = Form(...),
    timestamp: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Receive audio trigger from Vision OS Connect client.
    Returns: {status: "received", audio_event_id: str}
    """
    # TODO: Sprint 4.1 — audio-visual correlation
```

cameras.py:
```python
router = APIRouter(prefix="/cameras", tags=["cameras"])

@router.get("")
async def list_cameras(user: dict = Depends(get_current_user)):
    """List user's cameras. Returns: [{id, name, mode, enabled, location_id}]"""
    # TODO: query database

@router.post("")
async def add_camera(camera_data: dict, user: dict = Depends(get_current_user)):
    """Add new camera. Returns: {id, status: "created"}"""
    # TODO: validate + save to DB

@router.put("/{camera_id}")
async def update_camera(camera_id: str, updates: dict, user: dict = Depends(get_current_user)):
    """Update camera config. Returns: {status: "updated"}"""
    # TODO: update DB

@router.delete("/{camera_id}")
async def delete_camera(camera_id: str, user: dict = Depends(get_current_user)):
    """Remove camera. Returns: {status: "deleted"}"""
    # TODO: delete from DB + cleanup
```

users.py:
```python
router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
async def get_current_user_profile(user: dict = Depends(get_current_user)):
    """Get current user info + tier. Returns: {uid, email, tier, subscription_active, cameras_count}"""
    # TODO: query DB for full profile

@router.put("/me")
async def update_profile(updates: dict, user: dict = Depends(get_current_user)):
    """Update user profile. Returns: {status: "updated"}"""
    # TODO: validate + update DB
```

queries.py:
```python
router = APIRouter(prefix="/queries", tags=["queries"])

@router.post("")
async def submit_query(
    query_data: dict,
    user: dict = Depends(get_current_user)
):
    """Submit NL query (Household/Business only).
    Body: {question: str, cameras: list[str] | None, time_range: str | None}
    Returns: {answer: str, matching_events: list, thumbnails: list}
    """
    # TODO: Sprint 5.2 — call query_engine
```

TEST CASES TO WRITE (test_api.py):
```python
test_trigger_endpoint_accepts_jpeg()
test_trigger_endpoint_rejects_unauthenticated()
test_camera_crud()
test_query_endpoint_requires_premium()
```

OUTPUT: Generate all 4 API stub files with proper FastAPI routers, auth dependencies, placeholder responses, and test file. Each endpoint should return correct HTTP status codes.
```

---

## SPRINT 1.6 — GitHub Actions CI
### File: .github/workflows/test.yml (already created)
### Verify: CI pipeline runs correctly

```
The CI pipeline file is already created at .github/workflows/test.yml.
It includes:
- pgvector/pgvector:pg16 service container
- Python 3.11 setup with pip cache
- pytest with coverage (70% threshold)
- Black formatting check
- Ruff linting

To verify it works:
1. Push to GitHub
2. Check Actions tab
3. Fix any linting/formatting issues
4. Ensure all tests pass

The deploy.yml is also created for Cloud Run deployment.
It requires GitHub Secrets:
- GOOGLE_CLOUD_CREDENTIALS
- GOOGLE_CLOUD_PROJECT
- DATABASE_URL
- GEMINI_API_KEY
- OPENAI_API_KEY
- TELEGRAM_BOT_TOKEN
- CLOUD_SQL_INSTANCE
```

---

## Quick Reference: File Paths

| Sprint | File Path | 
|--------|-----------|
| 1.2 | `backend/storage/database.py` |
| 1.2 | `backend/tests/unit/test_database.py` |
| 1.3 | `backend/dashboard/auth.py` |
| 1.3 | `backend/tests/unit/test_auth.py` |
| 1.4 | `backend/ai/ai_client.py` |
| 1.4 | `backend/ai/groq_client.py` |
| 1.4 | `backend/tests/unit/test_ai_client.py` |
| 1.5 | `backend/api/triggers.py` |
| 1.5 | `backend/api/cameras.py` |
| 1.5 | `backend/api/users.py` |
| 1.5 | `backend/api/queries.py` |
| 1.5 | `backend/tests/unit/test_api.py` |

---

*Vision OS V1 — DeepSeek Coding Prompts*

*Copy, paste, generate, test, commit. Repeat.*
