"""add steps table

Revision ID: e3b2a9c1d4f6
Revises: c2d1f0a9e6b7
Create Date: 2025-12-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e3b2a9c1d4f6"
down_revision = "c2d1f0a9e6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("goal_id", sa.UUID(), nullable=False),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("done_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="planned"),
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
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["goals.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_steps_user_created_at",
        "steps",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_steps_user_created_at",
        table_name="steps",
    )
    op.drop_table("steps")
