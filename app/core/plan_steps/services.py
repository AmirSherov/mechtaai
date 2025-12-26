from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.plan_steps.models import Step
from app.core.plan_steps.schemas import StepIn
from app.response.response import APIError


def create_steps_batch(
    db: Session,
    user_id: UUID,
    steps: List[StepIn],
) -> List[Step]:
    if not steps:
        raise APIError(
            code="STEPS_EMPTY_BATCH",
            http_code=400,
            message="Список шагов пуст.",
        )

    created: List[Step] = []
    for step in steps:
        record = Step(
            user_id=user_id,
            goal_id=step.goal_id,
            level=step.level,
            title=step.title,
            description=step.description,
            planned_date=step.planned_date,
            status=step.status,
        )
        db.add(record)
        created.append(record)

    db.commit()
    for record in created:
        db.refresh(record)
    return created


def get_steps(
    db: Session,
    user_id: UUID,
    goal_id: UUID | None = None,
    level: str | None = None,
    status: str | None = None,
) -> List[Step]:
    query = db.query(Step).filter(Step.user_id == user_id)
    if goal_id:
        query = query.filter(Step.goal_id == goal_id)
    if level:
        query = query.filter(Step.level == level)
    if status:
        query = query.filter(Step.status == status)
    return query.order_by(desc(Step.created_at)).all()


def update_step(
    db: Session,
    user_id: UUID,
    step_id: UUID,
    payload: dict,
) -> Step:
    step = (
        db.query(Step)
        .filter(Step.user_id == user_id, Step.id == step_id)
        .first()
    )
    if step is None:
        raise APIError(
            code="STEP_NOT_FOUND",
            http_code=404,
            message="Шаг не найден.",
        )

    for key, value in payload.items():
        if hasattr(step, key):
            setattr(step, key, value)

    db.add(step)
    db.commit()
    db.refresh(step)
    return step


__all__ = [
    "create_steps_batch",
    "get_steps",
    "update_step",
]
