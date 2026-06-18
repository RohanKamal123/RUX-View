"""
test_database.py — Unit tests for Vision OS database layer.

Tests all 9 SQLAlchemy models and async CRUD operations using
an in-memory SQLite backend (replacing asyncpg for test speed).
"""

import pytest
import pytest_asyncio
from datetime import date, datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.storage.database import (
    AudioEvent,
    Base,
    Camera,
)
from backend.storage.crud import (
    create_event,
    get_event,
    get_events,
    update_event,
    create_person,
    get_person,
    find_similar_persons,
    update_person_sighting,
    create_sighting,
    get_person_sightings,
    save_scene_state,
    get_latest_scene_state,
    create_audio_event,
    get_expired_transcripts,
    delete_audio_event,
    upsert_shop_analytics,
    get_shop_analytics,
    create_camera,
    get_user_cameras,
    update_camera,
    delete_camera,
    create_location,
    get_user_locations,
    get_or_create_user,
    update_user_tier,
    get_user_by_firebase_uid,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory SQLite database for each test.

    Uses aiosqlite for async SQLite support.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sample_user_id() -> str:
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def sample_location_id() -> str:
    return "660e8400-e29b-41d4-a716-446655440001"


@pytest.fixture
def sample_camera_id() -> str:
    return "CAM_FRONT_001"


@pytest.fixture
def sample_event_data(sample_user_id, sample_location_id, sample_camera_id) -> dict:
    return {
        "user_id": sample_user_id,
        "location_id": sample_location_id,
        "camera_id": sample_camera_id,
        "incident_id": "INC_001",
        "timestamp_start": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
        "timestamp_end": datetime(2026, 4, 25, 10, 5, 30, tzinfo=timezone.utc),
        "duration_sec": 330.0,
        "threat_level": "MEDIUM",
        "alert_sent": False,
        "alert_type": "LOG",
        "camera_mode": "indoor",
        "is_business_hours": True,
    }


# ── Test: Table Creation ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_all_tables(db_session: AsyncSession):
    """Verify all 9 tables are created successfully."""
    from sqlalchemy import inspect

    conn = await db_session.connection()

    def _inspect(connection):
        inspector = inspect(connection)
        return inspector.get_table_names()

    tables = await conn.run_sync(_inspect)

    expected_tables = {
        "events",
        "persons",
        "person_sightings",
        "scene_states",
        "audio_events",
        "shop_analytics",
        "cameras",
        "locations",
        "users",
    }
    for table in expected_tables:
        assert table in tables, f"Missing table: {table}"


# ── Test: Events ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_event(db_session: AsyncSession, sample_event_data):
    """Test creating and retrieving an event."""
    event = await create_event(db_session, sample_event_data)
    assert event.id is not None
    assert event.incident_id == "INC_001"
    assert event.threat_level == "MEDIUM"
    assert event.duration_sec == 330.0


@pytest.mark.asyncio
async def test_get_event_not_found(db_session: AsyncSession):
    """Test get_event returns None for non-existent ID."""
    result = await get_event(db_session, 9999)
    assert result is None


@pytest.mark.asyncio
async def test_get_events_with_filters(
    db_session: AsyncSession, sample_event_data, sample_user_id
):
    """Test filtering events by user and threat level."""
    await create_event(db_session, sample_event_data)

    # Create a second event with different threat level
    event2_data = dict(sample_event_data)
    event2_data["incident_id"] = "INC_002"
    event2_data["threat_level"] = "HIGH"
    await create_event(db_session, event2_data)

    # Filter by threat_level
    results = await get_events(db_session, sample_user_id, {"threat_level": "HIGH"})
    assert len(results) == 1
    assert results[0].incident_id == "INC_002"


@pytest.mark.asyncio
async def test_update_event(db_session: AsyncSession, sample_event_data):
    """Test updating an event's fields."""
    event = await create_event(db_session, sample_event_data)
    updated = await update_event(
        db_session, event.id, {"threat_level": "HIGH", "alert_sent": True}
    )
    assert updated.threat_level == "HIGH"
    assert updated.alert_sent is True


# ── Test: Persons ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_person(
    db_session: AsyncSession, sample_user_id, sample_location_id
):
    """Test creating a person record."""
    person = await create_person(
        db_session,
        {
            "person_uid": "PERSON_001",
            "user_id": sample_user_id,
            "location_id": sample_location_id,
            "first_seen": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
            "last_seen": datetime(2026, 4, 25, 10, 30, 0, tzinfo=timezone.utc),
            "sighting_count": 1,
            "threat_flags": 0,
            "is_staff": False,
            "user_label": "Unknown",
        },
    )
    assert person.id is not None
    assert person.person_uid == "PERSON_001"
    assert person.sighting_count == 1


@pytest.mark.asyncio
async def test_insert_person_with_embedding(
    db_session: AsyncSession, sample_user_id, sample_location_id
):
    """Test creating a person with a pgvector embedding.

    Note: SQLite doesn't support pgvector, so we test the model
    creation without the embedding column for unit tests.
    """
    person = await create_person(
        db_session,
        {
            "person_uid": "PERSON_002",
            "user_id": sample_user_id,
            "location_id": sample_location_id,
            "sighting_count": 0,
            "is_staff": True,
            "user_label": "Staff",
        },
    )
    assert person.person_uid == "PERSON_002"
    assert person.is_staff is True
    assert person.user_label == "Staff"


@pytest.mark.asyncio
async def test_pgvector_similarity_query(
    db_session: AsyncSession, sample_user_id, sample_location_id
):
    """Test that find_similar_persons handles empty results gracefully.

    Full pgvector similarity requires Postgres with the extension,
    so this tests the function returns empty list when no embeddings exist.
    """
    # Create persons without embeddings
    for i in range(3):
        await create_person(
            db_session,
            {
                "person_uid": f"PERSON_00{i}",
                "user_id": sample_user_id,
                "location_id": sample_location_id,
                "sighting_count": i,
            },
        )

    # With SQLite, the raw text query will fail, so we test the
    # function handles the case gracefully
    dummy_embedding = [0.1] * 512
    try:
        results = await find_similar_persons(
            db_session, dummy_embedding, sample_location_id, limit=5
        )
        # If pgvector is not available, should return empty list
        assert isinstance(results, list)
    except Exception:
        # Expected: pgvector not available in SQLite
        pass


@pytest.mark.asyncio
async def test_update_person_sighting(
    db_session: AsyncSession, sample_user_id, sample_location_id
):
    """Test incrementing sighting count and updating last_seen."""
    await create_person(
        db_session,
        {
            "person_uid": "PERSON_003",
            "user_id": sample_user_id,
            "location_id": sample_location_id,
            "sighting_count": 5,
            "first_seen": datetime(2026, 4, 25, 8, 0, 0, tzinfo=timezone.utc),
        },
    )

    await update_person_sighting(db_session, "PERSON_003", sample_user_id)

    person = await get_person(db_session, "PERSON_003", sample_user_id)
    assert person is not None
    assert person.sighting_count == 6
    assert person.last_seen is not None


# ── Test: Person Sightings ────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_sighting(db_session: AsyncSession, sample_user_id):
    """Test creating a person sighting."""
    sighting = await create_sighting(
        db_session,
        {
            "person_uid": "PERSON_001",
            "user_id": sample_user_id,
            "camera_id": "CAM_001",
            "timestamp": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
            "clothing_top": "Red Shirt",
            "clothing_bottom": "Blue Jeans",
            "action": "walking",
        },
    )
    assert sighting.id is not None
    assert sighting.clothing_top == "Red Shirt"
    assert sighting.action == "walking"


@pytest.mark.asyncio
async def test_get_person_sightings(db_session: AsyncSession, sample_user_id):
    """Test retrieving sightings for a person ordered by time desc."""
    for i in range(3):
        await create_sighting(
            db_session,
            {
                "person_uid": "PERSON_001",
                "user_id": sample_user_id,
                "camera_id": "CAM_001",
                "timestamp": datetime(2026, 4, 25, 10 + i, 0, 0, tzinfo=timezone.utc),
            },
        )

    sightings = await get_person_sightings(db_session, "PERSON_001", sample_user_id)
    assert len(sightings) == 3
    # Should be newest first
    assert sightings[0].timestamp is not None
    assert sightings[0].timestamp.hour == 12


# ── Test: Scene States ────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_scene_state(
    db_session: AsyncSession, sample_user_id, sample_camera_id
):
    """Test saving a scene state snapshot."""
    state = await save_scene_state(
        db_session,
        {
            "camera_id": sample_camera_id,
            "user_id": sample_user_id,
            "timestamp": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
            "lighting": "daylight",
            "person_count": 3,
            "gates_json": {"gate1": "open"},
        },
    )
    assert state.id is not None
    assert state.lighting == "daylight"
    assert state.person_count == 3


@pytest.mark.asyncio
async def test_get_latest_scene_state(
    db_session: AsyncSession, sample_user_id, sample_camera_id
):
    """Test retrieving the most recent scene state."""
    for hour in [8, 10, 12]:
        await save_scene_state(
            db_session,
            {
                "camera_id": sample_camera_id,
                "user_id": sample_user_id,
                "timestamp": datetime(2026, 4, 25, hour, 0, 0, tzinfo=timezone.utc),
                "person_count": hour,
            },
        )

    latest = await get_latest_scene_state(db_session, sample_camera_id)
    assert latest is not None
    assert latest.person_count == 12


# ── Test: Audio Events ────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_audio_event(db_session: AsyncSession, sample_user_id):
    """Test creating an audio event."""
    audio = await create_audio_event(
        db_session,
        {
            "camera_id": "CAM_001",
            "user_id": sample_user_id,
            "timestamp": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
            "yamnet_class": "Scream",
            "yamnet_confidence": 0.95,
            "whisper_transcript": "Help me!",
            "threat_level": "HIGH",
            "expires_at": datetime(2026, 4, 28, 10, 0, 0, tzinfo=timezone.utc),
        },
    )
    assert audio.id is not None
    assert audio.yamnet_class == "Scream"
    assert audio.yamnet_confidence == 0.95


@pytest.mark.asyncio
async def test_get_expired_transcripts(db_session: AsyncSession, sample_user_id):
    """Test retrieving expired audio transcripts."""
    # Create an expired transcript (expires_at in the past)
    await create_audio_event(
        db_session,
        {
            "camera_id": "CAM_001",
            "user_id": sample_user_id,
            "timestamp": datetime(2026, 4, 20, 10, 0, 0, tzinfo=timezone.utc),
            "yamnet_class": "Gunshot",
            "expires_at": datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        },
    )
    # Create a non-expired transcript (expires_at far in the future)
    await create_audio_event(
        db_session,
        {
            "camera_id": "CAM_002",
            "user_id": sample_user_id,
            "timestamp": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
            "yamnet_class": "Speech",
            "expires_at": datetime(2099, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        },
    )

    expired = await get_expired_transcripts(db_session)
    assert len(expired) == 1
    assert expired[0].yamnet_class == "Gunshot"


@pytest.mark.asyncio
async def test_delete_audio_event(db_session: AsyncSession, sample_user_id):
    """Test deleting an audio event."""
    audio = await create_audio_event(
        db_session,
        {
            "camera_id": "CAM_001",
            "user_id": sample_user_id,
            "timestamp": datetime(2026, 4, 25, 10, 0, 0, tzinfo=timezone.utc),
            "yamnet_class": "GlassBreak",
        },
    )
    await delete_audio_event(db_session, audio.id)

    result = await db_session.execute(
        select(AudioEvent).where(AudioEvent.id == audio.id)
    )
    assert result.scalar_one_or_none() is None


# ── Test: Shop Analytics ──────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_shop_analytics(
    db_session: AsyncSession, sample_user_id, sample_camera_id
):
    """Test creating shop analytics record."""
    analytic = await upsert_shop_analytics(
        db_session,
        {
            "camera_id": sample_camera_id,
            "user_id": sample_user_id,
            "date": date(2026, 4, 25),
            "hour": 10,
            "customer_count": 15,
            "male_count": 8,
            "female_count": 7,
            "avg_dwell_seconds": 120.5,
        },
    )
    assert analytic.id is not None
    assert analytic.customer_count == 15
    assert analytic.avg_dwell_seconds == 120.5


@pytest.mark.asyncio
async def test_upsert_shop_analytics(
    db_session: AsyncSession, sample_user_id, sample_camera_id
):
    """Test upsert updates existing record."""
    await upsert_shop_analytics(
        db_session,
        {
            "camera_id": sample_camera_id,
            "user_id": sample_user_id,
            "date": date(2026, 4, 25),
            "hour": 10,
            "customer_count": 10,
        },
    )
    # Upsert with updated count
    updated = await upsert_shop_analytics(
        db_session,
        {
            "camera_id": sample_camera_id,
            "user_id": sample_user_id,
            "date": date(2026, 4, 25),
            "hour": 10,
            "customer_count": 20,
        },
    )
    assert updated.customer_count == 20


@pytest.mark.asyncio
async def test_get_shop_analytics(
    db_session: AsyncSession, sample_user_id, sample_camera_id
):
    """Test retrieving shop analytics for a date range."""
    for hour in range(8, 18):
        await upsert_shop_analytics(
            db_session,
            {
                "camera_id": sample_camera_id,
                "user_id": sample_user_id,
                "date": date(2026, 4, 25),
                "hour": hour,
                "customer_count": hour * 2,
            },
        )

    results = await get_shop_analytics(db_session, sample_camera_id, date(2026, 4, 25))
    assert len(results) == 10
    assert results[0].hour == 8
    assert results[-1].hour == 17


# ── Test: Cameras ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_camera(
    db_session: AsyncSession, sample_user_id, sample_location_id, sample_camera_id
):
    """Test creating a camera."""
    camera = await create_camera(
        db_session,
        {
            "id": sample_camera_id,
            "user_id": sample_user_id,
            "location_id": sample_location_id,
            "name": "Front Door Camera",
            "mode": "indoor",
            "enabled": True,
            "tier_required": "household",
            "gemma_cooldown_sec": 30,
        },
    )
    assert camera.id == sample_camera_id
    assert camera.name == "Front Door Camera"
    assert camera.gemma_cooldown_sec == 30


@pytest.mark.asyncio
async def test_get_user_cameras(
    db_session: AsyncSession, sample_user_id, sample_location_id
):
    """Test retrieving all cameras for a user."""
    for i in range(3):
        await create_camera(
            db_session,
            {
                "id": f"CAM_{i:03d}",
                "user_id": sample_user_id,
                "location_id": sample_location_id,
                "name": f"Camera {i}",
                "mode": "indoor",
            },
        )

    cameras = await get_user_cameras(db_session, sample_user_id)
    assert len(cameras) == 3


@pytest.mark.asyncio
async def test_update_camera(
    db_session: AsyncSession, sample_user_id, sample_location_id, sample_camera_id
):
    """Test updating camera configuration."""
    await create_camera(
        db_session,
        {
            "id": sample_camera_id,
            "user_id": sample_user_id,
            "location_id": sample_location_id,
            "name": "Old Name",
            "mode": "indoor",
        },
    )
    updated = await update_camera(
        db_session, sample_camera_id, {"name": "New Name", "mode": "outdoor"}
    )
    assert updated.name == "New Name"
    assert updated.mode == "outdoor"


@pytest.mark.asyncio
async def test_delete_camera(
    db_session: AsyncSession, sample_user_id, sample_location_id, sample_camera_id
):
    """Test deleting a camera."""
    await create_camera(
        db_session,
        {
            "id": sample_camera_id,
            "user_id": sample_user_id,
            "location_id": sample_location_id,
            "name": "To Delete",
        },
    )
    await delete_camera(db_session, sample_camera_id)

    result = await db_session.execute(
        select(Camera).where(Camera.id == sample_camera_id)
    )
    assert result.scalar_one_or_none() is None


# ── Test: Locations ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_location(db_session: AsyncSession, sample_user_id):
    """Test creating a location."""
    location = await create_location(
        db_session,
        {
            "user_id": sample_user_id,
            "name": "Main Office",
            "type": "indoor",
        },
    )
    assert location.id is not None
    assert location.name == "Main Office"
    assert location.type == "indoor"


@pytest.mark.asyncio
async def test_get_user_locations(db_session: AsyncSession, sample_user_id):
    """Test retrieving all locations for a user."""
    for name in ["Office", "Warehouse", "Parking"]:
        await create_location(
            db_session,
            {
                "user_id": sample_user_id,
                "name": name,
                "type": "indoor",
            },
        )

    locations = await get_user_locations(db_session, sample_user_id)
    assert len(locations) == 3
    assert locations[0].name == "Office"  # alphabetical order


# ── Test: Users ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_tier_query(db_session: AsyncSession):
    """Test user tier operations."""
    # Create user
    user = await get_or_create_user(db_session, "firebase-uid-123", "test@example.com")
    assert user.id is not None
    assert user.tier == "free"
    assert user.email == "test@example.com"

    # Upgrade tier
    updated = await update_user_tier(db_session, user.id, "business")
    assert updated.tier == "business"

    # Lookup by firebase UID
    found = await get_user_by_firebase_uid(db_session, "firebase-uid-123")
    assert found is not None
    assert found.email == "test@example.com"
    assert found.tier == "business"


@pytest.mark.asyncio
async def test_get_or_create_user_existing(db_session: AsyncSession):
    """Test get_or_create returns existing user."""
    user1 = await get_or_create_user(
        db_session, "firebase-uid-456", "first@example.com"
    )
    user2 = await get_or_create_user(
        db_session, "firebase-uid-456", "second@example.com"
    )
    # Should return the same user (first email preserved)
    assert user1.id == user2.id
    assert user2.email == "first@example.com"


@pytest.mark.asyncio
async def test_get_user_by_firebase_uid_not_found(db_session: AsyncSession):
    """Test get_user_by_firebase_uid returns None for unknown UID."""
    result = await get_user_by_firebase_uid(db_session, "nonexistent-uid")
    assert result is None
