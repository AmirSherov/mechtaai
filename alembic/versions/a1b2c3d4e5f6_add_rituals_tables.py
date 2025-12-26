"""add rituals tables

Revision ID: a1b2c3d4e5f6
Revises: e3b2a9c1d4f6
Create Date: 2025-12-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a1b2c3d4e5f6"
down_revision = "e3b2a9c1d4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mood_score", sa.Integer(), nullable=True),
        sa.Column("energy_score", sa.Integer(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
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
        "ix_journal_entries_user_date",
        "journal_entries",
        ["user_id", "date"],
    )

    op.create_table(
        "weekly_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("completed_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failed_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_reflection", sa.Text(), nullable=True),
        sa.Column("ai_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="in_progress"),
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
        "ix_weekly_reviews_user_week",
        "weekly_reviews",
        ["user_id", "week_start"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weekly_reviews_user_week",
        table_name="weekly_reviews",
    )
    op.drop_table("weekly_reviews")

    op.drop_index(
        "ix_journal_entries_user_date",
        table_name="journal_entries",
    )
    op.drop_table("journal_entries")
