from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.generate_goals.models import Goal, GoalGeneration
from app.core.generate_goals.schemas import GoalIn
from app.response.response import APIError


def create_generation_log(
    db: Session,
    user_id: UUID,
    comment_for_user: str | None,
    suggested_to_drop: list[dict],
) -> GoalGeneration:
    record = GoalGeneration(
        user_id=user_id,
        comment_for_user=comment_for_user,
        suggested_to_drop=suggested_to_drop or [],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_goals_batch(
    db: Session,
    user_id: UUID,
    goals: List[GoalIn],
) -> List[Goal]:
    if not goals:
        raise APIError(
            code="GOALS_EMPTY_BATCH",
            http_code=400,
            message="Список целей пуст.",
        )

    created: List[Goal] = []
    for goal in goals:
        record = Goal(
            user_id=user_id,
            area_id=goal.area_id,
            horizon=goal.horizon,
            title=goal.title,
            description=goal.description,
            metric=goal.metric,
            target_date=goal.target_date,
            priority=goal.priority,
            reason=goal.reason,
            status="planned",
        )
        db.add(record)
        created.append(record)

    db.commit()
    for record in created:
        db.refresh(record)
    return created


def get_goals(
    db: Session,
    user_id: UUID,
    horizon: str | None = None,
    status: str | None = None,
) -> List[Goal]:
    query = db.query(Goal).filter(Goal.user_id == user_id)
    if horizon:
        query = query.filter(Goal.horizon == horizon)
    if status:
        query = query.filter(Goal.status == status)
    return query.order_by(desc(Goal.created_at)).all()


def update_goal(
    db: Session,
    user_id: UUID,
    goal_id: UUID,
    payload: Dict,
) -> Goal:
    goal = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.id == goal_id)
        .first()
    )
    if goal is None:
        raise APIError(
            code="GOAL_NOT_FOUND",
            http_code=404,
            message="Цель не найдена.",
        )

    for key, value in payload.items():
        if hasattr(goal, key):
            setattr(goal, key, value)

    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_latest_generation(
    db: Session,
    user_id: UUID,
) -> GoalGeneration | None:
    return (
        db.query(GoalGeneration)
        .filter(GoalGeneration.user_id == user_id)
        .order_by(desc(GoalGeneration.created_at))
        .first()
    )


__all__ = [
    "create_generation_log",
    "create_goals_batch",
    "get_goals",
    "update_goal",
    "get_latest_generation",
]
