# Database Testing Guide — Vision OS

## Quick Start

```bash
# Run ALL tests (66 tests)
python -m pytest backend/tests/ -v

# Run ONLY database tests (28 tests)
python -m pytest backend/tests/unit/test_database.py -v

# Run with coverage report
python -m pytest backend/tests/ -v --cov=backend.storage --cov-report=term

# Run a single test
python -m pytest backend/tests/unit/test_database.py::test_user_tier_query -v
```

## What the Database Tests Cover

| Test Function | What It Tests |
|---|---|
| `test_create_all_tables` | All 9 tables created (events, persons, person_sightings, scene_states, audio_events, shop_analytics, cameras, locations, users) |
| `test_insert_event` | Create event, verify fields |
| `test_get_event_not_found` | Returns None for missing ID |
| `test_get_events_with_filters` | Filter by user + threat_level |
| `test_update_event` | Update threat_level, alert_sent |
| `test_insert_person` | Create person with all fields |
| `test_insert_person_with_embedding` | Create person (pgvector-safe) |
| `test_pgvector_similarity_query` | Graceful handling without pgvector |
| `test_update_person_sighting` | Increment sighting_count |
| `test_insert_sighting` | Create person sighting |
| `test_get_person_sightings` | Retrieve ordered by time desc |
| `test_insert_scene_state` | Save scene state snapshot |
| `test_get_latest_scene_state` | Get most recent state |
| `test_insert_audio_event` | Create audio event |
| `test_get_expired_transcripts` | Find expired transcripts |
| `test_delete_audio_event` | Delete audio event |
| `test_insert_shop_analytics` | Create shop analytics |
| `test_upsert_shop_analytics` | Upsert updates existing |
| `test_get_shop_analytics` | Get by date range |
| `test_insert_camera` | Create camera config |
| `test_get_user_cameras` | List user's cameras |
| `test_update_camera` | Update camera config |
| `test_delete_camera` | Delete camera |
| `test_insert_location` | Create location |
| `test_get_user_locations` | List user's locations |
| `test_user_tier_query` | User CRUD + tier upgrade |
| `test_get_or_create_user_existing` | Idempotent user creation |
| `test_get_user_by_firebase_uid_not_found` | Returns None for unknown UID |

## How Tests Work

The database tests use **SQLite in-memory** (`sqlite+aiosqlite:///:memory:`) instead of PostgreSQL. This means:

- ✅ **Fast** — no database server needed
- ✅ **Isolated** — each test gets a fresh database
- ✅ **No setup** — works immediately after `pip install`
- ⚠️ **pgvector not supported** — tests gracefully skip pgvector features

## Testing pgvector (PostgreSQL Only)

To test pgvector similarity search, you need a real PostgreSQL database with the pgvector extension:

### 1. Start PostgreSQL with pgvector

```bash
# Using Docker (recommended)
docker run -d \
  --name visionos-pgvector \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=visionos_test \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

### 2. Run Integration Tests

```bash
# Set the database URL
set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/visionos_test

# Run integration tests
python -m pytest backend/tests/integration/ -v
```

### 3. Create a pgvector Integration Test

If you want to write a dedicated pgvector test, create `backend/tests/integration/test_pgvector.py`:

```python
"""Integration tests for pgvector similarity search."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.storage.crud import create_person, find_similar_persons


@pytest.mark.asyncio
async def test_pgvector_similarity_search(db_session: AsyncSession):
    """Test actual pgvector cosine similarity."""
    # Create persons with embeddings
    person1 = await create_person(db_session, {
        "person_uid": "P1",
        "user_id": "user-1",
        "location_id": "loc-1",
        "embedding": [0.1] * 512,
    })
    person2 = await create_person(db_session, {
        "person_uid": "P2",
        "user_id": "user-1",
        "location_id": "loc-1",
        "embedding": [0.9] * 512,
    })

    # Search with embedding similar to person1
    results = await find_similar_persons(
        db_session,
        embedding=[0.11] * 512,
        location_id="loc-1",
        limit=5,
    )
    assert len(results) > 0
    assert results[0]["person_uid"] == "P1"
```

## Test Architecture

```
backend/tests/
├── conftest.py              # Shared fixtures (sample images, audio, mock users)
├── unit/
│   ├── test_database.py     # Database CRUD tests (28 tests)
│   ├── test_ai_client.py    # AI client tests (13 tests)
│   ├── test_api.py          # API endpoint tests (11 tests)
│   └── test_auth.py         # Authentication tests (14 tests)
├── integration/             # Integration tests (requires Postgres)
│   └── __init__.py
├── e2e/                     # End-to-end tests
│   └── __init__.py
└── fixtures/                # Test data fixtures
    └── __init__.py
```

## Current Test Results

```
66 passed in 10.37s
Coverage: 93% (backend.storage)
  - crud.py:     88%
  - database.py: 99%
```
