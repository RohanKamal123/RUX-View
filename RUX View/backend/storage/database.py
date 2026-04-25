"""
database.py — SQLAlchemy 2.0 async models for Vision OS.

9 tables: events, persons, person_sightings, scene_states,
audio_events, shop_analytics, cameras, locations, users.

Uses pgvector for person embeddings.
"""

import uuid
from datetime import date, datetime, time
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Declarative base for all Vision OS models."""
    pass


# ── Events ────────────────────────────────────────────────────


class Event(Base):
    """Security events detected by cameras."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    location_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    camera_id: Mapped[str] = mapped_column(String(100), nullable=False)
    incident_id: Mapped[str] = mapped_column(String(100), nullable=False)
    timestamp_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    timestamp_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threat_level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    camera_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_business_hours: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    gemma_raw_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    gemini_decision: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timeline_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    person_sightings = relationship("PersonSighting", back_populates="event")
    audio_events = relationship("AudioEvent", back_populates="event")


# ── Persons (with pgvector) ───────────────────────────────────


class Person(Base):
    """Tracked persons with ReID embedding vector."""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_uid: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    location_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    first_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sighting_count: Mapped[int] = mapped_column(Integer, default=0)
    threat_flags: Mapped[int] = mapped_column(Integer, default=0)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    user_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    appearance_history: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(512), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("person_uid", "user_id", name="uq_person_uid_user"),
    )


# ── Person Sightings ──────────────────────────────────────────


class PersonSighting(Base):
    """Individual sighting of a person during an event."""

    __tablename__ = "person_sightings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_uid: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=True
    )
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    clothing_top: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clothing_bottom: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clothing_colors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accessories: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hand_objects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    anomaly_signals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[Any]] = mapped_column(Vector(512), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    event = relationship("Event", back_populates="person_sightings")


# ── Scene States ──────────────────────────────────────────────


class SceneState(Base):
    """Snapshot of a camera's scene at a point in time."""

    __tablename__ = "scene_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    gates_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    doors_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    vehicles_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    lighting: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    person_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_scene_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


# ── Audio Events ──────────────────────────────────────────────


class AudioEvent(Base):
    """Audio detection events from YAMNet + Whisper."""

    __tablename__ = "audio_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=True
    )
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    yamnet_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    yamnet_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    whisper_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gemini_interpretation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    threat_level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    has_visual_match: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    event = relationship("Event", back_populates="audio_events")


# ── Shop Analytics ────────────────────────────────────────────


class ShopAnalytic(Base):
    """Hourly shop analytics aggregated from camera feeds."""

    __tablename__ = "shop_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    customer_count: Mapped[int] = mapped_column(Integer, default=0)
    male_count: Mapped[int] = mapped_column(Integer, default=0)
    female_count: Mapped[int] = mapped_column(Integer, default=0)
    unknown_gender: Mapped[int] = mapped_column(Integer, default=0)
    age_teens: Mapped[int] = mapped_column(Integer, default=0)
    age_20s: Mapped[int] = mapped_column(Integer, default=0)
    age_30s: Mapped[int] = mapped_column(Integer, default=0)
    age_40s: Mapped[int] = mapped_column(Integer, default=0)
    age_50plus: Mapped[int] = mapped_column(Integer, default=0)
    avg_dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "camera_id", "date", "hour", name="uq_shop_analytics_camera_date_hour"
        ),
    )


# ── Cameras ───────────────────────────────────────────────────


class Camera(Base):
    """Camera device configuration."""

    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    location_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tier_required: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gemma_cooldown_sec: Mapped[int] = mapped_column(Integer, default=15)
    ignore_zones_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    shop_hours_open: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    shop_hours_close: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    night_hours_start: Mapped[Optional[time]] = mapped_column(
        Time, default=time(22, 0)
    )
    night_hours_end: Mapped[Optional[time]] = mapped_column(
        Time, default=time(6, 0)
    )
    loiter_config_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Locations ─────────────────────────────────────────────────


class Location(Base):
    """Physical location grouping cameras."""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    camera_topology: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Users ─────────────────────────────────────────────────────


class User(Base):
    """Vision OS user accounts."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    firebase_uid: Mapped[Optional[str]] = mapped_column(
        String(200), unique=True, nullable=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    telegram_bot_token: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    tier: Mapped[str] = mapped_column(String(20), default="free")
    trial_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subscription_active: Mapped[bool] = mapped_column(Boolean, default=False)
    bkash_subscriber_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    secondary_contact: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
