"""add wants analysis table

Revision ID: b7c5c1a0d2f1
Revises: 3b6d1e0f7a2c
Create Date: 2025-12-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b7c5c1a0d2f1"
down_revision = "3b6d1e0f7a2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wants_analysis",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("top_wants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("top_pains", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("focus_areas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("patterns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_comment", sa.Text(), nullable=False),
        sa.Column("suggested_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        "ix_wants_analysis_user_created_at",
        "wants_analysis",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wants_analysis_user_created_at",
        table_name="wants_analysis",
    )
    op.drop_table("wants_analysis")
