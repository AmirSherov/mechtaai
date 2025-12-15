"""add life_wheel tables

Revision ID: abcd1234efgh
Revises: 98f0f25bfa08
Create Date: 2025-12-03 22:45:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "abcd1234efgh"
down_revision = "98f0f25bfa08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_wheels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_life_wheels_user_id_created_at",
        "life_wheels",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_life_wheels_user_id_created_at",
        table_name="life_wheels",
    )
    op.drop_table("life_wheels")

