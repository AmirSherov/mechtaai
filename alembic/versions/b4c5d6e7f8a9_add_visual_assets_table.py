"""add visual assets table

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f6
Create Date: 2025-12-24 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b4c5d6e7f8a9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visual_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("image_key", sa.String(), nullable=False),
        sa.Column("local_path", sa.String(), nullable=False),
        sa.Column("ai_prompt", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="dall-e-3"),
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
        "ix_visual_assets_user_entity",
        "visual_assets",
        ["user_id", "entity_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_visual_assets_user_entity",
        table_name="visual_assets",
    )
    op.drop_table("visual_assets")
