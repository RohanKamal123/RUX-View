"""Add payments table for bKash/Nagad transaction tracking.

Revision ID: 002
Revises: 001
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("amount_bdt", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.String(100), nullable=False),
        sa.Column("payment_method", sa.String(20), server_default="bkash"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("payments")
