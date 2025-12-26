from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


FutureStoryDraftStatus = Literal["in_progress", "completed"]


class FutureStoryQuestion(BaseModel):
    area_id: str
    question: str


class FutureStoryDraftIn(BaseModel):
    area_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=10_000)


class FutureStoryDraftPublic(BaseModel):
    id: UUID
    user_id: UUID
    answers: list[dict]
    status: FutureStoryDraftStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FutureStoryByArea(BaseModel):
    area_id: str
    title: str
    paragraph: str


class FutureStoryHorizon(BaseModel):
    full_text: str
    by_area: list[FutureStoryByArea]


class FutureStoryKeyImage(BaseModel):
    id: str
    text: str | None = None
    text_ru: str | None = None
    dall_e_prompt: str | None = None


class FutureStoryPublic(BaseModel):
    id: UUID
    user_id: UUID
    horizon_3y: FutureStoryHorizon
    horizon_5y: FutureStoryHorizon
    key_images: list[FutureStoryKeyImage]
    validation_notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FutureStoryUpdateIn(BaseModel):
    horizon: Literal["3y", "5y"]
    full_text: str = Field(..., min_length=1)
    by_area: list[FutureStoryByArea]


class FutureStoryAIResponse(BaseModel):
    future_story_3y: FutureStoryHorizon
    future_story_5y: FutureStoryHorizon
    key_images: list[FutureStoryKeyImage]
    validation_notes: str | None = None


__all__ = [
    "FutureStoryQuestion",
    "FutureStoryDraftIn",
    "FutureStoryDraftPublic",
    "FutureStoryByArea",
    "FutureStoryHorizon",
    "FutureStoryKeyImage",
    "FutureStoryPublic",
    "FutureStoryUpdateIn",
    "FutureStoryAIResponse",
]
