"""add telegram_id to users

Revision ID: f2b3c4d5e6f7
Revises: d1e2f3a4b5c6
Create Date: 2025-12-26 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f2b3c4d5e6f7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_users_telegram_id",
        "users",
        ["telegram_id"],
    )
    op.create_index(
        "ix_users_telegram_id",
        "users",
        ["telegram_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_constraint(
        "uq_users_telegram_id",
        "users",
        type_="unique",
    )
    op.drop_column("users", "telegram_id")
