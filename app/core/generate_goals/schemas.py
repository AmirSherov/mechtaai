from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


GoalHorizon = Literal["1y", "3y", "5y", "2026", "to_36"]
GoalStatus = Literal["draft", "planned", "in_progress", "done", "dropped"]


class GoalPublic(BaseModel):
    id: UUID
    user_id: UUID
    area_id: str
    horizon: GoalHorizon
    title: str
    description: str | None = None
    metric: str | None = None
    target_date: date | None = None
    priority: int
    reason: str | None = None
    status: GoalStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoalIn(BaseModel):
    area_id: str = Field(..., min_length=1)
    horizon: GoalHorizon
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    metric: str | None = Field(default=None, max_length=100)
    target_date: date | None = None
    priority: int = Field(default=1, ge=1, le=99)
    reason: str | None = Field(default=None, max_length=1000)
    status: GoalStatus | None = None


class GoalsBatchIn(BaseModel):
    goals: list[GoalIn]


class GoalsGenerateIn(BaseModel):
    limits: dict | None = None


class GoalSuggestedDrop(BaseModel):
    text: str
    reason: str


class GoalAIGenerated(BaseModel):
    id: str
    area_id: str
    title: str
    description: str | None = None
    metric: str | None = None
    target_date: date | None = None
    reason: str | None = None
    priority: int


class GoalsAIResponse(BaseModel):
    goals_1y: list[GoalAIGenerated]
    goals_3y: list[GoalAIGenerated]
    goals_5y: list[GoalAIGenerated]
    comment_for_user: str
    suggested_to_drop: list[GoalSuggestedDrop]


class GoalGenerationPublic(BaseModel):
    id: UUID
    user_id: UUID
    comment_for_user: str | None = None
    suggested_to_drop: list[GoalSuggestedDrop]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "GoalHorizon",
    "GoalStatus",
    "GoalPublic",
    "GoalIn",
    "GoalsBatchIn",
    "GoalsGenerateIn",
    "GoalSuggestedDrop",
    "GoalAIGenerated",
    "GoalsAIResponse",
    "GoalGenerationPublic",
]
