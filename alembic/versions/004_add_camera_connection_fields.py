"""Add rtsp_url/connection_type/p2p_* fields to cameras (idempotent).

rtsp_url previously had no backing column at all -- the add-camera API
accepted it but pg_crud.upsert_camera() silently discarded it, so every
camera's RTSP URL was lost on creation and always read back empty.
p2p_* fields support Dahua P2P cloud-relay cameras (same serial +
username + password auth model as the DMSS app) as an alternative to a
directly-reachable RTSP URL. p2p_password_encrypted is written via
backend.core.crypto.encrypt_secret -- never stored in plaintext.

Revision ID: 004
Revises: 003
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("cameras")]

    if "connection_type" not in columns:
        op.add_column(
            "cameras",
            sa.Column("connection_type", sa.String(20), nullable=False, server_default="rtsp"),
        )
    if "rtsp_url" not in columns:
        op.add_column("cameras", sa.Column("rtsp_url", sa.String(500), nullable=True))
    if "p2p_serial" not in columns:
        op.add_column("cameras", sa.Column("p2p_serial", sa.String(100), nullable=True))
    if "p2p_username" not in columns:
        op.add_column("cameras", sa.Column("p2p_username", sa.String(100), nullable=True))
    if "p2p_password_encrypted" not in columns:
        op.add_column("cameras", sa.Column("p2p_password_encrypted", sa.String(500), nullable=True))
    if "rtmp_stream_key" not in columns:
        op.add_column("cameras", sa.Column("rtmp_stream_key", sa.String(64), nullable=True, unique=True))


def downgrade() -> None:
    op.drop_column("cameras", "rtmp_stream_key")
    op.drop_column("cameras", "p2p_password_encrypted")
    op.drop_column("cameras", "p2p_username")
    op.drop_column("cameras", "p2p_serial")
    op.drop_column("cameras", "rtsp_url")
    op.drop_column("cameras", "connection_type")
