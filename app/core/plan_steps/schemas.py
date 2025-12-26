from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


StepLevel = Literal["year", "quarter", "month", "week", "day"]
StepStatus = Literal["planned", "in_progress", "done", "skipped"]


class StepsGenerateIn(BaseModel):
    goal_ids: list[UUID] = Field(..., min_length=1, max_length=10)
    current_load_hint: dict | None = None
    year_bounds: dict | None = None


class StepPublic(BaseModel):
    id: UUID
    user_id: UUID
    goal_id: UUID
    level: StepLevel
    title: str
    description: str | None = None
    planned_date: date | None = None
    done_date: date | None = None
    status: StepStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StepIn(BaseModel):
    goal_id: UUID
    level: StepLevel
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    planned_date: date | None = None
    status: StepStatus = "planned"


class StepsBatchIn(BaseModel):
    steps: list[StepIn]


class PlanStepAction(BaseModel):
    id: str
    title: str
    description: str | None = None


class PlanStepQuarter(BaseModel):
    quarter_id: str
    summary: str
    key_actions: list[PlanStepAction]


class PlanStepMonthlyHint(BaseModel):
    month: str
    focus: str


class PlanStepWeeklyAction(BaseModel):
    id: str
    title: str
    frequency_per_week: int


class PlanStepWeeklyTemplate(BaseModel):
    name: str
    recommended_actions: list[PlanStepWeeklyAction]


class PlanStepGoalPlan(BaseModel):
    goal_id: str
    quarters: list[PlanStepQuarter]
    monthly_hints: list[PlanStepMonthlyHint]
    weekly_templates: list[PlanStepWeeklyTemplate]


class PlanStepsAIResponse(BaseModel):
    plan_by_goal: list[PlanStepGoalPlan]
    overload_warning: str | None = None
    comment_for_user: str


__all__ = [
    "StepLevel",
    "StepStatus",
    "StepsGenerateIn",
    "StepPublic",
    "StepIn",
    "StepsBatchIn",
    "PlanStepAction",
    "PlanStepQuarter",
    "PlanStepMonthlyHint",
    "PlanStepWeeklyAction",
    "PlanStepWeeklyTemplate",
    "PlanStepGoalPlan",
    "PlanStepsAIResponse",
]
