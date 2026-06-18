# CONTEXT.md — Storage Module
# Module: backend/storage/
# Sprint: 1.2
# Purpose: Database schema, connection management, data retention

---

## What This Module Does

Manages all database operations for Vision OS. Uses SQLAlchemy 2.0 with async
sessions against Cloud SQL Postgres with pgvector extension enabled.

Two files:
- **database.py** — Schema definitions, connection pool, CRUD operations
- **cleanup.py** — Data retention jobs (delete old events per tier)

---

## Database Schema (9 Tables)

### events
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
  threat_level        VARCHAR(10),        -- LOW/MEDIUM/HIGH
  alert_sent          BOOLEAN DEFAULT FALSE,
  alert_type          VARCHAR(30),        -- LOG/TEXT/PHOTO/EMERGENCY
  camera_mode         VARCHAR(20),        -- indoor/outdoor/parking/shop/mixed
  is_business_hours   BOOLEAN,
  gemma_raw_json      JSONB,
  gemini_decision     JSONB,
  timeline_json       JSONB,             -- all burst observations
  thumbnail_url       TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

### persons (with pgvector)
```sql
CREATE TABLE persons (
  id                  SERIAL PRIMARY KEY,
  person_uid          VARCHAR(20) NOT NULL,  -- PERSON_007
  user_id             UUID NOT NULL,
  location_id         UUID NOT NULL,
  first_seen          TIMESTAMPTZ,
  last_seen           TIMESTAMPTZ,
  sighting_count      INTEGER DEFAULT 0,
  threat_flags        INTEGER DEFAULT 0,
  is_staff            BOOLEAN DEFAULT FALSE,
  user_label          VARCHAR(100),          -- "Postman", "Gardener"
  appearance_history  JSONB,
  embedding           vector(512),           -- pgvector: BoxMOT/FastReID embedding
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(person_uid, user_id)
);
```

### person_sightings
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
```

### scene_states, audio_events, shop_analytics, cameras, locations, users
See ARCHITECTURE.md Section 10 for full schemas.

---

## Key Decisions

- **D022** — pgvector for embedding storage, NOT separate vector DB
- **D013** — Cloud SQL Postgres, NOT Firestore (need complex queries)
- **D026** — All DB calls must be async (await)

## pgvector Index
```sql
CREATE INDEX ON persons USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## Retention Policy
- Free: 7 days
- Household: 30 days
- Business: 90 days
- Audio transcripts: 1-3 days

## Dependencies
- sqlalchemy 2.0 (async)
- psycopg2-binary
- pgvector
- alembic (migrations)

## Called By
- backend/api/*.py
- backend/core/pipeline.py
- backend/ai/reid_engine.py
- backend/analytics/*.py
- backend/alerts/alert_router.py
