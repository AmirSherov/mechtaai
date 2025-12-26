from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.generate_goals.schemas import (
    GoalIn,
    GoalPublic,
    GoalsBatchIn,
    GoalsGenerateIn,
)
from app.core.generate_goals.models import Goal
from app.core.generate_goals.services import create_goals_batch, get_goals, update_goal
from app.core.gamification.services import (
    ActionType,
    award_action,
    build_gamification_event,
    merge_award_results,
)
from app.response import StandardResponse, make_success_response
from app.response.response import APIError
from mechtaai_bg_worker.celery_app import celery_app


router = APIRouter(prefix="/goals", tags=["goals"])


@router.post(
    "/generate",
    response_model=StandardResponse,
    summary="Сгенерировать цели (AI)",
)
def goals_generate_view(
    payload: GoalsGenerateIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    _ = db
    task = celery_app.send_task(
        "goals.generate",
        args=[str(user.id), payload.model_dump() if payload else None],
    )
    timeout_seconds = settings.ai_proxy_timeout_seconds + 30
    try:
        result = task.get(timeout=timeout_seconds)
    except CeleryTimeoutError:
        raise APIError(
            code="GOALS_AI_TIMEOUT",
            http_code=504,
            message="Goals generation timed out.",
        )

    if not result or not result.get("ok"):
        error = (result or {}).get("error") or {}
        raise APIError(
            code=error.get("code", "GOALS_AI_FAILED"),
            http_code=error.get("http_code", 500),
            message=error.get("message", "Goals generation failed."),
        )

    return make_success_response(result=result["payload"])


@router.post(
    "/batch",
    response_model=StandardResponse,
    summary="Сохранить цели пачкой",
)
def goals_batch_view(
    payload: GoalsBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    goals = create_goals_batch(db=db, user_id=user.id, goals=payload.goals)
    award_results = [
        award_action(db, user.id, ActionType.GOAL_CREATED) for _ in goals
    ]
    merged = merge_award_results(award_results)
    event = build_gamification_event(ActionType.GOAL_CREATED, merged)
    result_items = [GoalPublic.model_validate(g).model_dump(mode="json") for g in goals]
    payload_result = {
        "items": result_items,
        "gamification_event": event,
    }
    return make_success_response(result=payload_result)


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить цели",
)
def goals_list_view(
    horizon: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    goals = get_goals(db=db, user_id=user.id, horizon=horizon, status=status)
    result = [GoalPublic.model_validate(g).model_dump(mode="json") for g in goals]
    return make_success_response(result=result)


@router.put(
    "/{goal_id}",
    response_model=StandardResponse,
    summary="Обновить цель",
)
def goals_update_view(
    goal_id: UUID,
    payload: GoalIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    data: Dict = payload.model_dump(exclude_none=True)
    existing = (
        db.query(Goal)
        .filter(Goal.user_id == user.id, Goal.id == goal_id)
        .first()
    )
    previous_status = existing.status if existing else None
    goal = update_goal(db=db, user_id=user.id, goal_id=goal_id, payload=data)
    gamification_event = None
    if previous_status != "done" and goal.status == "done":
        horizon = (goal.horizon or "").lower()
        small_horizons = {"quarter", "q1", "q2", "q3", "q4"}
        action = (
            ActionType.GOAL_ACHIEVED_SMALL
            if horizon in small_horizons
            else ActionType.GOAL_ACHIEVED_BIG
        )
        award_result = award_action(db, user.id, action)
        gamification_event = build_gamification_event(action, award_result)
    result = GoalPublic.model_validate(goal).model_dump(mode="json")
    result["gamification_event"] = gamification_event
    return make_success_response(result=result)


__all__ = ["router"]
