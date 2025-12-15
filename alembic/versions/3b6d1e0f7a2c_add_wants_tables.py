"""add wants tables

Revision ID: 3b6d1e0f7a2c
Revises: d854eec51add
Create Date: 2025-12-15 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3b6d1e0f7a2c"
down_revision = "d854eec51add"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create enum types explicitly (idempotent), and disable implicit
    # CREATE TYPE during table creation to avoid "type already exists"
    wants_raw_status = postgresql.ENUM(
        "draft",
        "completed",
        name="wants_raw_status",
        create_type=False,
    )
    wants_raw_chunk_exercise = postgresql.ENUM(
        "stream",
        "future_me",
        name="wants_raw_chunk_exercise",
        create_type=False,
    )

    wants_raw_status.create(op.get_bind(), checkfirst=True)
    wants_raw_chunk_exercise.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "wants_raw",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            wants_raw_status,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("stream_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "stream_timer_seconds",
            sa.Integer(),
            nullable=False,
            server_default="600",
        ),
        sa.Column("raw_wants_stream", sa.Text(), nullable=True),
        sa.Column("stream_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_future_me", sa.Text(), nullable=True),
        sa.Column(
            "future_me_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("raw_envy", sa.Text(), nullable=True),
        sa.Column("raw_regrets", sa.Text(), nullable=True),
        sa.Column("raw_what_to_do_5y", sa.Text(), nullable=True),
        sa.Column(
            "reverse_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        "idx_wants_raw_user_updated",
        "wants_raw",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "uq_wants_raw_user_draft",
        "wants_raw",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )

    op.create_table(
        "wants_raw_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wants_raw_id", sa.UUID(), nullable=False),
        sa.Column("exercise", wants_raw_chunk_exercise, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["wants_raw_id"],
            ["wants_raw.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_wants_raw_chunks_wants_raw_id_created_at",
        "wants_raw_chunks",
        ["wants_raw_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wants_raw_chunks_wants_raw_id_created_at",
        table_name="wants_raw_chunks",
    )
    op.drop_table("wants_raw_chunks")

    op.drop_index("uq_wants_raw_user_draft", table_name="wants_raw")
    op.drop_index("idx_wants_raw_user_updated", table_name="wants_raw")
    op.drop_table("wants_raw")

    postgresql.ENUM(name="wants_raw_chunk_exercise").drop(
        op.get_bind(),
        checkfirst=True,
    )
    postgresql.ENUM(name="wants_raw_status").drop(
        op.get_bind(), checkfirst=True
    )
