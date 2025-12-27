from __future__ import annotations

from typing import Dict, List
from uuid import UUID

from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.plan_steps.schemas import (
    StepIn,
    StepPublic,
    StepsBatchIn,
    StepsGenerateIn,
)
from app.core.plan_steps.models import Step
from app.core.plan_steps.services import (
    create_steps_batch,
    delete_step,
    get_steps,
    update_step,
)
from app.core.gamification.services import (
    ActionType,
    award_action,
    build_gamification_event,
)
from app.core.limits.dependencies import check_text_quota
from app.response import StandardResponse, make_success_response
from app.response.response import APIError
from mechtaai_bg_worker.celery_app import celery_app


router = APIRouter(prefix="/steps", tags=["steps"])


@router.post(
    "/generate",
    response_model=StandardResponse,
    dependencies=[Depends(check_text_quota)],
    summary="Сгенерировать план шагов",
)
def steps_generate_view(
    payload: StepsGenerateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    _ = db
    task = celery_app.send_task(
        "steps.generate",
        args=[str(user.id), payload.model_dump()],
    )
    timeout_seconds = settings.ai_proxy_timeout_seconds + 30
    try:
        result = task.get(timeout=timeout_seconds)
    except CeleryTimeoutError:
        raise APIError(
            code="STEPS_AI_TIMEOUT",
            http_code=504,
            message="Steps generation timed out.",
        )

    if not result or not result.get("ok"):
        error = (result or {}).get("error") or {}
        raise APIError(
            code=error.get("code", "STEPS_AI_FAILED"),
            http_code=error.get("http_code", 500),
            message=error.get("message", "Steps generation failed."),
        )

    return make_success_response(result=result["payload"])


@router.post(
    "/batch",
    response_model=StandardResponse,
    summary="Сохранить шаги пачкой",
)
def steps_batch_view(
    payload: StepsBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    steps = create_steps_batch(db=db, user_id=user.id, steps=payload.steps)
    result = [StepPublic.model_validate(s).model_dump(mode="json") for s in steps]
    return make_success_response(result=result)


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить шаги",
)
def steps_list_view(
    goal_id: UUID | None = Query(default=None),
    level: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    steps = get_steps(
        db=db,
        user_id=user.id,
        goal_id=goal_id,
        level=level,
        status=status,
    )
    result = [StepPublic.model_validate(s).model_dump(mode="json") for s in steps]
    return make_success_response(result=result)


@router.put(
    "/{step_id}",
    response_model=StandardResponse,
    summary="Обновить шаг",
)
def steps_update_view(
    step_id: UUID,
    payload: StepIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    data: Dict = payload.model_dump()
    existing = (
        db.query(Step)
        .filter(Step.user_id == user.id, Step.id == step_id)
        .first()
    )
    previous_status = existing.status if existing else None
    step = update_step(db=db, user_id=user.id, step_id=step_id, payload=data)
    gamification_event = None
    if previous_status != "done" and step.status == "done":
        award_result = award_action(db, user.id, ActionType.GOAL_STEP_COMPLETED)
        gamification_event = build_gamification_event(
            ActionType.GOAL_STEP_COMPLETED,
            award_result,
        )
    result = StepPublic.model_validate(step).model_dump(mode="json")
    result["gamification_event"] = gamification_event
    return make_success_response(result=result)


@router.delete(
    "/{step_id}",
    response_model=StandardResponse,
    summary="Delete step",
)
def steps_delete_view(
    step_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    delete_step(db=db, user_id=user.id, step_id=step_id)
    return make_success_response(result={"success": True})


__all__ = ["router"]
