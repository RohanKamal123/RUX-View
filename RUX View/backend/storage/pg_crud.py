"""
pg_crud.py — PostgreSQL CRUD Layer for Vision OS (Hybrid Dual-Write).

This module provides PostgreSQL-backed CRUD operations for:
- Events (motion/audio triggers)
- Persons (ReID embeddings with pgvector)
- Person Sightings
- Scene States
- Audio Events
- Shop Analytics
- Cameras
- Locations
- Users
- API Keys

Hybrid Architecture:
  Layer 1 (MEGA.nz): Media blobs (images, audio clips, thumbnails)
  Layer 2 (Neon PG): Structured data, vectors, events, metadata

Usage:
    from backend.storage.pg_crud import PostgresCRUD

    crud = PostgresCRUD()
    event = await crud.create_event(user_id="...", camera_id="...", ...)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func, desc

from backend.storage.database import (
    Event,
    Person,
    PersonSighting,
    Camera,
    User,
    Payment,
)
from backend.storage.engine import create_session

logger = logging.getLogger(__name__)


class PostgresCRUD:
    """PostgreSQL CRUD operations for Vision OS structured data.

    All methods are async and use the engine's session factory.
    Media blobs (images, audio) are NOT stored here — they go to MEGA.nz.
    """

    # ── Events ─────────────────────────────────────────────────────────────

    async def create_event(
        self,
        user_id: str,
        location_id: str,
        camera_id: str,
        incident_id: str,
        timestamp_start: datetime,
        timestamp_end: Optional[datetime] = None,
        duration_sec: Optional[float] = None,
        threat_level: Optional[str] = None,
        alert_sent: bool = False,
        alert_type: Optional[str] = None,
        camera_mode: Optional[str] = None,
        is_business_hours: Optional[bool] = None,
        gemma_raw_json: Optional[dict] = None,
        gemini_decision: Optional[dict] = None,
        timeline_json: Optional[dict] = None,
        thumbnail_url: Optional[str] = None,
    ) -> Event:
        """Create a new security event."""
        async with create_session() as session:
            event = Event(
                user_id=user_id,
                location_id=location_id,
                camera_id=camera_id,
                incident_id=incident_id,
                timestamp_start=timestamp_start,
                timestamp_end=timestamp_end,
                duration_sec=duration_sec,
                threat_level=threat_level,
                alert_sent=alert_sent,
                alert_type=alert_type,
                camera_mode=camera_mode,
                is_business_hours=is_business_hours,
                gemma_raw_json=gemma_raw_json,
                gemini_decision=gemini_decision,
                timeline_json=timeline_json,
                thumbnail_url=thumbnail_url,
            )
            session.add(event)
            await session.flush()
            await session.refresh(event)
            logger.debug("Created event %d for camera %s", event.id, camera_id)
            return event

    async def get_event(self, event_id: int) -> Optional[Event]:
        """Get an event by ID."""
        async with create_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            return result.scalar_one_or_none()

    async def get_user_events(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        camera_id: Optional[str] = None,
    ) -> list[Event]:
        """Get events for a user, with optional camera filter."""
        async with create_session() as session:
            query = select(Event).where(Event.user_id == user_id)
            if camera_id:
                query = query.where(Event.camera_id == camera_id)
            query = query.order_by(desc(Event.timestamp_start)).limit(limit).offset(offset)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def count_user_events(self, user_id: str) -> int:
        """Count total events for a user."""
        async with create_session() as session:
            result = await session.execute(
                select(func.count(Event.id)).where(Event.user_id == user_id)
            )
            return result.scalar() or 0

    # ── Persons (with pgvector) ────────────────────────────────────────────

    async def upsert_person(
        self,
        person_uid: str,
        user_id: str,
        location_id: str,
        embedding: Optional[Any] = None,
        is_staff: bool = False,
        user_label: Optional[str] = None,
        appearance_history: Optional[dict] = None,
    ) -> Person:
        """Create or update a person record.

        If a person with the same person_uid + user_id exists, update it.
        Otherwise, create a new record.
        """
        async with create_session() as session:
            result = await session.execute(
                select(Person).where(
                    Person.person_uid == person_uid,
                    Person.user_id == user_id,
                )
            )
            person = result.scalar_one_or_none()

            now = datetime.now(timezone.utc)

            if person:
                person.last_seen = now
                person.sighting_count = (person.sighting_count or 0) + 1
                if embedding is not None:
                    person.embedding = embedding
                if user_label is not None:
                    person.user_label = user_label
                if appearance_history is not None:
                    person.appearance_history = appearance_history
                person.is_staff = is_staff
            else:
                person = Person(
                    person_uid=person_uid,
                    user_id=user_id,
                    location_id=location_id,
                    first_seen=now,
                    last_seen=now,
                    sighting_count=1,
                    embedding=embedding,
                    is_staff=is_staff,
                    user_label=user_label,
                    appearance_history=appearance_history,
                )
                session.add(person)

            await session.flush()
            await session.refresh(person)
            return person

    async def find_similar_persons(
        self,
        embedding: list[float],
        user_id: str,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> list[tuple[Person, float]]:
        """Find persons with similar embeddings using cosine distance."""
        async with create_session() as session:
            query = (
                select(
                    Person,
                    Person.embedding.cosine_distance(embedding).label("distance"),
                )
                .where(
                    Person.user_id == user_id,
                    Person.embedding.isnot(None),
                )
                .having(
                    Person.embedding.cosine_distance(embedding) <= threshold
                )
                .order_by("distance")
                .limit(limit)
            )
            result = await session.execute(query)
            return [(row[0], row[1]) for row in result.all()]

    async def get_person(self, person_uid: str, user_id: str) -> Optional[Person]:
        """Get a person by UID and user."""
        async with create_session() as session:
            result = await session.execute(
                select(Person).where(
                    Person.person_uid == person_uid,
                    Person.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    # ── Person Sightings ───────────────────────────────────────────────────

    async def create_sighting(
        self,
        person_uid: str,
        user_id: str,
        event_id: Optional[int] = None,
        camera_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        clothing_top: Optional[str] = None,
        clothing_bottom: Optional[str] = None,
        clothing_colors: Optional[str] = None,
        accessories: Optional[str] = None,
        hand_objects: Optional[str] = None,
        action: Optional[str] = None,
        anomaly_signals: Optional[str] = None,
        embedding: Optional[Any] = None,
        thumbnail_url: Optional[str] = None,
    ) -> PersonSighting:
        """Record a person sighting during an event."""
        async with create_session() as session:
            sighting = PersonSighting(
                person_uid=person_uid,
                user_id=user_id,
                event_id=event_id,
                camera_id=camera_id,
                timestamp=timestamp or datetime.now(timezone.utc),
                clothing_top=clothing_top,
                clothing_bottom=clothing_bottom,
                clothing_colors=clothing_colors,
                accessories=accessories,
                hand_objects=hand_objects,
                action=action,
                anomaly_signals=anomaly_signals,
                embedding=embedding,
                thumbnail_url=thumbnail_url,
            )
            session.add(sighting)
            await session.flush()
            await session.refresh(sighting)
            return sighting

    # ── Cameras ────────────────────────────────────────────────────────────

    async def upsert_camera(
        self,
        camera_id: str,
        user_id: str,
        location_id: str,
        name: Optional[str] = None,
        mode: Optional[str] = None,
        enabled: bool = True,
        tier_required: Optional[str] = None,
    ) -> Camera:
        """Create or update a camera configuration."""
        async with create_session() as session:
            result = await session.execute(
                select(Camera).where(Camera.id == camera_id)
            )
            cam = result.scalar_one_or_none()

            if cam:
                cam.name = name or cam.name
                cam.mode = mode or cam.mode
                cam.enabled = enabled
                cam.tier_required = tier_required or cam.tier_required
            else:
                cam = Camera(
                    id=camera_id,
                    user_id=user_id,
                    location_id=location_id,
                    name=name,
                    mode=mode,
                    enabled=enabled,
                    tier_required=tier_required,
                )
                session.add(cam)

            await session.flush()
            await session.refresh(cam)
            return cam

    async def get_user_cameras(self, user_id: str) -> list[Camera]:
        """Get all cameras for a user."""
        async with create_session() as session:
            result = await session.execute(
                select(Camera).where(Camera.user_id == user_id)
            )
            return list(result.scalars().all())

    # ── Users ──────────────────────────────────────────────────────────────

    async def upsert_user(
        self,
        user_id: str,
        firebase_uid: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tier: str = "free",
        subscription_active: bool = False,
    ) -> User:
        """Create or update a user record."""
        async with create_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                if email is not None:
                    user.email = email
                if phone is not None:
                    user.phone = phone
                user.tier = tier
                user.subscription_active = subscription_active
            else:
                user = User(
                    id=user_id,
                    firebase_uid=firebase_uid,
                    email=email,
                    phone=phone,
                    tier=tier,
                    subscription_active=subscription_active,
                )
                session.add(user)

            await session.flush()
            await session.refresh(user)
            return user

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        async with create_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()

    # ── Payments ───────────────────────────────────────────────────────────

    async def create_payment(
        self,
        user_id: str,
        tier: str,
        amount_bdt: int,
        transaction_id: str,
        payment_method: str = "bkash",
        notes: Optional[str] = None,
    ) -> Payment:
        """Record a new payment transaction."""
        async with create_session() as session:
            payment = Payment(
                user_id=user_id,
                tier=tier,
                amount_bdt=amount_bdt,
                transaction_id=transaction_id,
                payment_method=payment_method,
                status="pending",
                notes=notes,
            )
            session.add(payment)
            await session.flush()
            await session.refresh(payment)
            logger.info("Payment recorded: %s for tier %s (BDT %d)", transaction_id, tier, amount_bdt)
            return payment

    async def get_user_payments(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Payment]:
        """Get payment history for a user."""
        async with create_session() as session:
            query = (
                select(Payment)
                .where(Payment.user_id == user_id)
                .order_by(desc(Payment.created_at))
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    # ── Health ─────────────────────────────────────────────────────────────

    async def check_health(self) -> dict:
        """Check database connectivity and pgvector availability."""
        try:
            async with create_session() as session:
                result = await session.execute(select(func.now()))
                db_time = result.scalar()

                result = await session.execute(
                    __import__("sqlalchemy").text(
                        "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"
                    )
                )
                vector_row = result.fetchone()

                return {
                    "status": "ok",
                    "db_time": str(db_time),
                    "pgvector": vector_row[1] if vector_row else "not installed",
                }
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return {"status": "error", "error": str(e)}
