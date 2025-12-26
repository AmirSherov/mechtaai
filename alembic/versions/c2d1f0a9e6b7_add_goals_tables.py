"""add goals tables

Revision ID: c2d1f0a9e6b7
Revises: f4a2c9e8d1b3
Create Date: 2025-12-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c2d1f0a9e6b7"
down_revision = "f4a2c9e8d1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("area_id", sa.String(), nullable=False),
        sa.Column("horizon", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric", sa.String(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_goals_user_created_at",
        "goals",
        ["user_id", "created_at"],
    )

    op.create_table(
        "goal_generations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("comment_for_user", sa.Text(), nullable=True),
        sa.Column(
            "suggested_to_drop",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
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
        "ix_goal_generations_user_created_at",
        "goal_generations",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_goal_generations_user_created_at",
        table_name="goal_generations",
    )
    op.drop_table("goal_generations")

    op.drop_index(
        "ix_goals_user_created_at",
        table_name="goals",
    )
    op.drop_table("goals")
