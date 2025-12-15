from __future__ import annotations

from datetime import datetime
from typing import Dict
from uuid import UUID

from pydantic import BaseModel, Field, conint
from pydantic.config import ConfigDict


ScoreValue = conint(ge=0, le=10)


class LifeWheelBase(BaseModel):
    scores: Dict[str, ScoreValue] = Field(
        ...,
        description="Карта оценок по сферам: {area_id: score (0-10)}",
    )
    note: str | None = None


class LifeWheelCreate(LifeWheelBase):
    pass


class LifeWheelPublic(LifeWheelBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = ["LifeWheelCreate", "LifeWheelPublic"]
