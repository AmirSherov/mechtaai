from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel
from pydantic.config import ConfigDict


PromoDuration = Literal["month", "6m", "year"]


class PromoCodePublic(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    duration_code: PromoDuration
    expires_at: Optional[datetime]
    is_active: bool
    redemptions_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromoCodeCreate(BaseModel):
    name: str
    duration_code: PromoDuration
    expires_at: datetime


class PromoCodeUpdate(BaseModel):
    name: str | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class PromoCodeActivateRequest(BaseModel):
    code: str


class PromoCodeActivateResponse(BaseModel):
    code: str
    duration_code: PromoDuration
    subscription_expires_at: datetime


__all__ = [
    "PromoDuration",
    "PromoCodePublic",
    "PromoCodeCreate",
    "PromoCodeUpdate",
    "PromoCodeActivateRequest",
    "PromoCodeActivateResponse",
]
