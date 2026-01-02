from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel
from pydantic.config import ConfigDict


SubscriptionDuration = Literal["month", "6m", "year"]


class TelegramCreateInvoiceRequest(BaseModel):
    telegram_id: int
    duration: SubscriptionDuration


class TelegramInvoicePrice(BaseModel):
    label: str
    amount: int  # minor units (kopeks)


class TelegramCreateInvoiceResponse(BaseModel):
    purchase_id: uuid.UUID
    invoice_payload: str
    title: str
    description: str
    currency: str
    prices: list[TelegramInvoicePrice]
    duration: SubscriptionDuration
    amount: int

    model_config = ConfigDict(from_attributes=True)


class TelegramPreCheckoutValidateRequest(BaseModel):
    telegram_id: int
    invoice_payload: str
    currency: str
    total_amount: int


class TelegramPreCheckoutValidateResponse(BaseModel):
    allowed: bool


class TelegramSuccessfulPaymentRequest(BaseModel):
    telegram_id: int
    invoice_payload: str
    currency: str
    total_amount: int
    telegram_payment_charge_id: str
    provider_payment_charge_id: str
    raw_successful_payment: dict[str, Any] | None = None


class TelegramSuccessfulPaymentResponse(BaseModel):
    purchase_id: uuid.UUID
    status: str
    subscription_expires_at: datetime

