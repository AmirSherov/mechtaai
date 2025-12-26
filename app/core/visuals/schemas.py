from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class VisualGenerateIn(BaseModel):
    story_id: UUID
    image_key: str = Field(..., min_length=1)


class VisualRegenerateIn(BaseModel):
    asset_id: UUID


class VisualAssetPublic(BaseModel):
    id: UUID
    user_id: UUID
    entity_type: str
    entity_id: UUID
    image_key: str
    local_path: str
    ai_prompt: str
    provider: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "VisualGenerateIn",
    "VisualRegenerateIn",
    "VisualAssetPublic",
]
