"""add future story tables

Revision ID: f4a2c9e8d1b3
Revises: b7c5c1a0d2f1
Create Date: 2025-12-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f4a2c9e8d1b3"
down_revision = "b7c5c1a0d2f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "future_story_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="in_progress",
        ),
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
        "ix_future_story_drafts_user_updated",
        "future_story_drafts",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "future_stories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("horizon_3y", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("horizon_5y", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("key_images", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_notes", sa.Text(), nullable=True),
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
        "ix_future_stories_user_created_at",
        "future_stories",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_future_stories_user_created_at",
        table_name="future_stories",
    )
    op.drop_table("future_stories")

    op.drop_index(
        "ix_future_story_drafts_user_updated",
        table_name="future_story_drafts",
    )
    op.drop_table("future_story_drafts")
