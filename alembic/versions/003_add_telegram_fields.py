"""Add telegram_chat_id to users if missing (idempotent).

Revision ID: 003
Revises: 002_add_payments
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002_add_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: add telegram_chat_id column if it doesn't exist yet
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("users")]
    if "telegram_chat_id" not in columns:
        op.add_column("users", sa.Column("telegram_chat_id", sa.String(50), nullable=True))
    if "telegram_bot_token" not in columns:
        op.add_column("users", sa.Column("telegram_bot_token", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_bot_token")
    op.drop_column("users", "telegram_chat_id")