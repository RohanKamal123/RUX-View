"""
crud.py — Async CRUD operations for Vision OS database layer.

All functions are async and use SQLAlchemy 2.0 async sessions.
Includes pgvector similarity search for person embeddings.
"""

from datetime import date, datetime, timezone
from typing import Any, AsyncGenerator

from sqlalchemy import and_, delete, desc, select, text, update
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.storage.database import (
    AudioEvent,
    Base,
    Camera,
    Event,
    Location,
    Person,
    PersonSighting,
    SceneState,
    ShopAnalytic,
    User,
)

# ── Connection ────────────────────────────────────────────────

_engine: Any = None
_session_factory: Any = None


async def init_db(database_url: str | None = None) -> None:
    """Initialize database engine and create all tables.

    Args:
        database_url: Postgres connection string. Defaults to env var.
    """
    global _engine, _session_factory

    if database_url is None:
        from os import environ

        database_url = environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/visionos",
        )

    _engine = create_async_engine(
        database_url, echo=False, pool_size=10, max_overflow=20
    )
    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async DB session.

    Usage:
        @app.get("/events")
        async def list_events(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _session_factory is None:
        await init_db()

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Events CRUD ───────────────────────────────────────────────


async def create_event(db: AsyncSession, event_data: dict) -> Event:
    """Create a new security event."""
    event = Event(**event_data)
    db.add(event)
    await db.flush()
    await db.refresh(event)
    return event


async def get_event(db: AsyncSession, event_id: int) -> Event | None:
    """Get a single event by ID."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    return result.scalar_one_or_none()


async def get_events(
    db: AsyncSession, user_id: str, filters: dict | None = None
) -> list[Event]:
    """Get events for a user with optional filters.

    Supported filters:
        - location_id: str
        - camera_id: str
        - threat_level: str
        - limit: int (default 50)
        - offset: int (default 0)
    """
    filters = filters or {}
    query = select(Event).where(Event.user_id == user_id)

    if "location_id" in filters:
        query = query.where(Event.location_id == filters["location_id"])
    if "camera_id" in filters:
        query = query.where(Event.camera_id == filters["camera_id"])
    if "threat_level" in filters:
        query = query.where(Event.threat_level == filters["threat_level"])

    query = query.order_by(desc(Event.timestamp_start))
    query = query.limit(filters.get("limit", 50)).offset(filters.get("offset", 0))

    result = await db.execute(query)
    return list(result.scalars().all())


async def update_event(db: AsyncSession, event_id: int, updates: dict) -> Event:
    """Update an event and return the updated record."""
    await db.execute(update(Event).where(Event.id == event_id).values(**updates))
    await db.flush()
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one()
    await db.refresh(event)
    return event


# ── Persons CRUD (with pgvector) ──────────────────────────────


async def create_person(db: AsyncSession, person_data: dict) -> Person:
    """Create a new person record (may include embedding)."""
    person = Person(**person_data)
    db.add(person)
    await db.flush()
    await db.refresh(person)
    return person


async def get_person(db: AsyncSession, person_uid: str, user_id: str) -> Person | None:
    """Get a person by UID and user."""
    result = await db.execute(
        select(Person).where(
            and_(Person.person_uid == person_uid, Person.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def find_similar_persons(
    db: AsyncSession,
    embedding: list[float],
    location_id: str,
    limit: int = 5,
) -> list[dict]:
    """Find persons with similar embeddings using pgvector cosine similarity.

    Args:
        db: Database session.
        embedding: 512-dimension embedding vector.
        location_id: Filter by location.
        limit: Max results.

    Returns:
        List of dicts with person data and similarity score.
    """
    if db is None:
        logger.error("find_similar_persons called with db=None — skipping")
        return []
    stmt = text("""
        SELECT id, person_uid, user_id, location_id, first_seen, last_seen,
               sighting_count, threat_flags, is_staff, user_label,
               1 - (embedding <=> :embedding) AS similarity
        FROM persons
        WHERE location_id = :location_id
          AND embedding IS NOT NULL
        ORDER BY embedding <=> :embedding
        LIMIT :limit
        """)
    result = await db.execute(
        stmt,
        {
            "embedding": str(embedding),
            "location_id": location_id,
            "limit": limit,
        },
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


async def update_person_sighting(
    db: AsyncSession, person_uid: str, user_id: str
) -> None:
    """Increment sighting count and update last_seen for a person."""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Person)
        .where(and_(Person.person_uid == person_uid, Person.user_id == user_id))
        .values(
            sighting_count=Person.sighting_count + 1,
            last_seen=now,
        )
    )
    await db.flush()


# ── Person Sightings ──────────────────────────────────────────


async def create_sighting(db: AsyncSession, sighting_data: dict) -> PersonSighting:
    """Create a new person sighting record."""
    sighting = PersonSighting(**sighting_data)
    db.add(sighting)
    await db.flush()
    await db.refresh(sighting)
    return sighting


async def get_person_sightings(
    db: AsyncSession, person_uid: str, user_id: str
) -> list[PersonSighting]:
    """Get all sightings for a person, newest first."""
    result = await db.execute(
        select(PersonSighting)
        .where(
            and_(
                PersonSighting.person_uid == person_uid,
                PersonSighting.user_id == user_id,
            )
        )
        .order_by(desc(PersonSighting.timestamp))
    )
    return list(result.scalars().all())


# ── Scene States ──────────────────────────────────────────────


async def save_scene_state(db: AsyncSession, state_data: dict) -> SceneState:
    """Save a new scene state snapshot."""
    state = SceneState(**state_data)
    db.add(state)
    await db.flush()
    await db.refresh(state)
    return state


async def get_latest_scene_state(db: AsyncSession, camera_id: str) -> SceneState | None:
    """Get the most recent scene state for a camera."""
    result = await db.execute(
        select(SceneState)
        .where(SceneState.camera_id == camera_id)
        .order_by(desc(SceneState.timestamp))
        .limit(1)
    )
    return result.scalar_one_or_none()


# ── Audio Events ──────────────────────────────────────────────


async def create_audio_event(db: AsyncSession, audio_data: dict) -> AudioEvent:
    """Create a new audio event record."""
    audio = AudioEvent(**audio_data)
    db.add(audio)
    await db.flush()
    await db.refresh(audio)
    return audio


async def get_expired_transcripts(db: AsyncSession) -> list[AudioEvent]:
    """Get audio events where expires_at is in the past."""
    now = datetime.now(timezone.utc)
    result = await db.execute(select(AudioEvent).where(AudioEvent.expires_at < now))
    return list(result.scalars().all())


async def delete_audio_event(db: AsyncSession, event_id: int) -> None:
    """Delete an audio event by ID."""
    await db.execute(delete(AudioEvent).where(AudioEvent.id == event_id))
    await db.flush()


# ── Shop Analytics ────────────────────────────────────────────


async def upsert_shop_analytics(db: AsyncSession, analytics_data: dict) -> ShopAnalytic:
    """Insert or update shop analytics for a camera/date/hour.

    Uses ON CONFLICT to upsert.
    """
    # Try to find existing record
    result = await db.execute(
        select(ShopAnalytic).where(
            and_(
                ShopAnalytic.camera_id == analytics_data["camera_id"],
                ShopAnalytic.date == analytics_data["date"],
                ShopAnalytic.hour == analytics_data["hour"],
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        for key, value in analytics_data.items():
            if key != "id" and value is not None:
                setattr(existing, key, value)
        await db.flush()
        await db.refresh(existing)
        return existing
    else:
        analytic = ShopAnalytic(**analytics_data)
        db.add(analytic)
        await db.flush()
        await db.refresh(analytic)
        return analytic


async def get_shop_analytics(
    db: AsyncSession, camera_id: str, date_val: date
) -> list[ShopAnalytic]:
    """Get shop analytics for a camera on a specific date."""
    result = await db.execute(
        select(ShopAnalytic)
        .where(
            and_(
                ShopAnalytic.camera_id == camera_id,
                ShopAnalytic.date == date_val,
            )
        )
        .order_by(ShopAnalytic.hour)
    )
    return list(result.scalars().all())


# ── Cameras ───────────────────────────────────────────────────


async def create_camera(db: AsyncSession, camera_data: dict) -> Camera:
    """Register a new camera."""
    camera = Camera(**camera_data)
    db.add(camera)
    await db.flush()
    await db.refresh(camera)
    return camera


async def get_user_cameras(db: AsyncSession, user_id: str) -> list[Camera]:
    """Get all cameras for a user."""
    result = await db.execute(
        select(Camera).where(Camera.user_id == user_id).order_by(Camera.name)
    )
    return list(result.scalars().all())


async def update_camera(db: AsyncSession, camera_id: str, updates: dict) -> Camera:
    """Update camera configuration."""
    await db.execute(update(Camera).where(Camera.id == camera_id).values(**updates))
    await db.flush()
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one()
    await db.refresh(camera)
    return camera


async def delete_camera(db: AsyncSession, camera_id: str) -> None:
    """Delete a camera by ID."""
    await db.execute(delete(Camera).where(Camera.id == camera_id))
    await db.flush()


# ── Locations ─────────────────────────────────────────────────


async def create_location(db: AsyncSession, location_data: dict) -> Location:
    """Create a new location."""
    location = Location(**location_data)
    db.add(location)
    await db.flush()
    await db.refresh(location)
    return location


async def get_user_locations(db: AsyncSession, user_id: str) -> list[Location]:
    """Get all locations for a user."""
    result = await db.execute(
        select(Location).where(Location.user_id == user_id).order_by(Location.name)
    )
    return list(result.scalars().all())


# ── Users ─────────────────────────────────────────────────────


async def get_or_create_user(db: AsyncSession, firebase_uid: str, email: str) -> User:
    """Find user by Firebase UID or create a new one."""
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(firebase_uid=firebase_uid, email=email)
        db.add(user)
        await db.flush()
        await db.refresh(user)

    return user


async def update_user_tier(db: AsyncSession, user_id: str, tier: str) -> User:
    """Update a user's subscription tier."""
    await db.execute(update(User).where(User.id == user_id).values(tier=tier))
    await db.flush()
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()
    await db.refresh(user)
    return user


async def get_user_by_firebase_uid(db: AsyncSession, firebase_uid: str) -> User | None:
    """Look up a user by their Firebase authentication UID."""
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    return result.scalar_one_or_none()
