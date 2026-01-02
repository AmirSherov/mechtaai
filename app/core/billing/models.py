from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database.base import Base


class SubscriptionPurchase(Base):
    __tablename__ = "subscription_purchases"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    plan_tier = Column(String, nullable=False, default="pro")
    duration_code = Column(String, nullable=False)  # month|6m|year

    amount = Column(Integer, nullable=False)  # in minor units (kopeks)
    currency = Column(String, nullable=False, default="RUB")

    status = Column(String, nullable=False, default="pending")

    invoice_payload = Column(String, nullable=False, unique=True, index=True)
    telegram_payment_charge_id = Column(String, nullable=True, unique=True)
    provider_payment_charge_id = Column(String, nullable=True, unique=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    paid_at = Column(DateTime(timezone=True), nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    raw_successful_payment = Column(JSONB, nullable=True)

    user = relationship("User")


__all__ = ["SubscriptionPurchase"]

