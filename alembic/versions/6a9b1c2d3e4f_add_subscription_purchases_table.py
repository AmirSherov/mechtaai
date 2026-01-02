"""add subscription_purchases table

Revision ID: 6a9b1c2d3e4f
Revises: c07ef7e7cd22
Create Date: 2025-12-29 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "6a9b1c2d3e4f"
down_revision = "c07ef7e7cd22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_tier", sa.String(), nullable=False, server_default="pro"),
        sa.Column("duration_code", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="RUB"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("invoice_payload", sa.String(), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(), nullable=True),
        sa.Column("provider_payment_charge_id", sa.String(), nullable=True),
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
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_successful_payment", postgresql.JSONB(), nullable=True),
    )

    op.create_index(
        "ix_subscription_purchases_user_id",
        "subscription_purchases",
        ["user_id"],
    )
    op.create_unique_constraint(
        "uq_subscription_purchases_invoice_payload",
        "subscription_purchases",
        ["invoice_payload"],
    )
    op.create_index(
        "ix_subscription_purchases_invoice_payload",
        "subscription_purchases",
        ["invoice_payload"],
    )
    op.create_unique_constraint(
        "uq_subscription_purchases_telegram_payment_charge_id",
        "subscription_purchases",
        ["telegram_payment_charge_id"],
    )
    op.create_unique_constraint(
        "uq_subscription_purchases_provider_payment_charge_id",
        "subscription_purchases",
        ["provider_payment_charge_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_subscription_purchases_provider_payment_charge_id",
        "subscription_purchases",
        type_="unique",
    )
    op.drop_constraint(
        "uq_subscription_purchases_telegram_payment_charge_id",
        "subscription_purchases",
        type_="unique",
    )
    op.drop_index(
        "ix_subscription_purchases_invoice_payload",
        table_name="subscription_purchases",
    )
    op.drop_constraint(
        "uq_subscription_purchases_invoice_payload",
        "subscription_purchases",
        type_="unique",
    )
    op.drop_index("ix_subscription_purchases_user_id", table_name="subscription_purchases")
    op.drop_table("subscription_purchases")

