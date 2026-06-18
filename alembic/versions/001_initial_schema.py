"""Initial schema — all Vision OS tables with pgvector support.

Revision ID: 001
Revises:
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enable pgvector extension ──────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Events ─────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("camera_id", sa.String(100), nullable=False),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("timestamp_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("threat_level", sa.String(10), nullable=True),
        sa.Column("alert_sent", sa.Boolean(), default=False),
        sa.Column("alert_type", sa.String(30), nullable=True),
        sa.Column("camera_mode", sa.String(20), nullable=True),
        sa.Column("is_business_hours", sa.Boolean(), nullable=True),
        sa.Column("gemma_raw_json", sa.JSON(), nullable=True),
        sa.Column("gemini_decision", sa.JSON(), nullable=True),
        sa.Column("timeline_json", sa.JSON(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Persons (with pgvector) ────────────────────────────────────────────
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_uid", sa.String(20), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sighting_count", sa.Integer(), default=0),
        sa.Column("threat_flags", sa.Integer(), default=0),
        sa.Column("is_staff", sa.Boolean(), default=False),
        sa.Column("user_label", sa.String(100), nullable=True),
        sa.Column("appearance_history", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_uid", "user_id", name="uq_person_uid_user"),
    )

    # ── Person Sightings ───────────────────────────────────────────────────
    op.create_table(
        "person_sightings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("person_uid", sa.String(20), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("camera_id", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clothing_top", sa.Text(), nullable=True),
        sa.Column("clothing_bottom", sa.Text(), nullable=True),
        sa.Column("clothing_colors", sa.Text(), nullable=True),
        sa.Column("accessories", sa.Text(), nullable=True),
        sa.Column("hand_objects", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("anomaly_signals", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(512), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"],),
    )

    # ── Scene States ───────────────────────────────────────────────────────
    op.create_table(
        "scene_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gates_json", sa.JSON(), nullable=True),
        sa.Column("doors_json", sa.JSON(), nullable=True),
        sa.Column("vehicles_json", sa.JSON(), nullable=True),
        sa.Column("lighting", sa.String(30), nullable=True),
        sa.Column("person_count", sa.Integer(), nullable=True),
        sa.Column("raw_scene_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Audio Events ───────────────────────────────────────────────────────
    op.create_table(
        "audio_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("camera_id", sa.String(100), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yamnet_class", sa.String(100), nullable=True),
        sa.Column("yamnet_confidence", sa.Float(), nullable=True),
        sa.Column("whisper_transcript", sa.Text(), nullable=True),
        sa.Column("gemini_interpretation", sa.Text(), nullable=True),
        sa.Column("threat_level", sa.String(10), nullable=True),
        sa.Column("has_visual_match", sa.Boolean(), default=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"],),
    )

    # ── Shop Analytics ─────────────────────────────────────────────────────
    op.create_table(
        "shop_analytics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("customer_count", sa.Integer(), default=0, server_default="0"),
        sa.Column("male_count", sa.Integer(), default=0, server_default="0"),
        sa.Column("female_count", sa.Integer(), default=0, server_default="0"),
        sa.Column("unknown_gender", sa.Integer(), default=0, server_default="0"),
        sa.Column("age_teens", sa.Integer(), default=0, server_default="0"),
        sa.Column("age_20s", sa.Integer(), default=0, server_default="0"),
        sa.Column("age_30s", sa.Integer(), default=0, server_default="0"),
        sa.Column("age_40s", sa.Integer(), default=0, server_default="0"),
        sa.Column("age_50plus", sa.Integer(), default=0, server_default="0"),
        sa.Column("avg_dwell_seconds", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("camera_id", "date", "hour", name="uq_shop_analytics_camera_date_hour"),
    )

    # ── Cameras ────────────────────────────────────────────────────────────
    op.create_table(
        "cameras",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("location_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("mode", sa.String(20), nullable=True),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("tier_required", sa.String(20), nullable=True),
        sa.Column("gemma_cooldown_sec", sa.Integer(), default=15),
        sa.Column("ignore_zones_json", sa.JSON(), nullable=True),
        sa.Column("shop_hours_open", sa.Time(), nullable=True),
        sa.Column("shop_hours_close", sa.Time(), nullable=True),
        sa.Column("night_hours_start", sa.Time(), default=sa.text("'22:00'")),
        sa.Column("night_hours_end", sa.Time(), default=sa.text("'06:00'")),
        sa.Column("loiter_config_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Locations ──────────────────────────────────────────────────────────
    op.create_table(
        "locations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("type", sa.String(30), nullable=True),
        sa.Column("camera_topology", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("firebase_uid", sa.String(200), nullable=True, unique=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("telegram_chat_id", sa.String(50), nullable=True),
        sa.Column("telegram_bot_token", sa.String(200), nullable=True),
        sa.Column("tier", sa.String(20), default="free"),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subscription_active", sa.Boolean(), default=False),
        sa.Column("bkash_subscriber_id", sa.String(200), nullable=True),
        sa.Column("secondary_contact", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── API Keys ───────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False, default={}),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_prefix", "key_hash", name="uq_api_key_prefix_hash"),
    )

    # ── API Key Usage ──────────────────────────────────────────────────────
    op.create_table(
        "api_key_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["key_id"], ["api_keys.id"],),
        sa.UniqueConstraint("key_id", "timestamp", name="uq_key_timestamp"),
    )


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table("api_key_usage")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("locations")
    op.drop_table("cameras")
    op.drop_table("shop_analytics")
    op.drop_table("audio_events")
    op.drop_table("scene_states")
    op.drop_table("person_sightings")
    op.drop_table("persons")
    op.drop_table("events")
