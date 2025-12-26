from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from app.core.plan_steps.schemas import StepPublic


JournalEntryType = Literal["morning", "evening"]
WeeklyReviewStatus = Literal["in_progress", "completed", "auto_archived"]


class RitualsTodayStatus(BaseModel):
    date: date
    morning_done: bool
    evening_done: bool
    interception: dict | None = None


class JournalEntryIn(BaseModel):
    type: JournalEntryType
    answers: dict
    mood_score: int | None = Field(default=None, ge=1, le=10)
    energy_score: int | None = Field(default=None, ge=1, le=10)


class JournalEntryPublic(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    type: JournalEntryType
    answers: dict
    mood_score: int | None
    energy_score: int | None
    ai_feedback: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklyAnalyzeIn(BaseModel):
    user_reflection: str = Field(..., min_length=1, max_length=5000)


class WeeklyReviewPublic(BaseModel):
    id: UUID
    user_id: UUID
    week_start: date
    week_end: date
    completed_steps: list
    failed_steps: list
    user_reflection: str | None
    ai_analysis: dict | None
    status: WeeklyReviewStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WeeklyCommitIn(BaseModel):
    next_week_step_ids: list[UUID] = Field(..., min_length=1)


class WeeklyReviewAIResponse(BaseModel):
    summary: str
    score: int
    feedback: dict
    questions_for_reflection: list[str]


__all__ = [
    "RitualsTodayStatus",
    "JournalEntryIn",
    "JournalEntryPublic",
    "WeeklyAnalyzeIn",
    "WeeklyReviewPublic",
    "WeeklyCommitIn",
    "WeeklyReviewAIResponse",
    "StepPublic",
]
