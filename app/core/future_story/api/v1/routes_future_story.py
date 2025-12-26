from __future__ import annotations

from typing import Dict, List

from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, Depends
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.core.areas.models import Area
from app.core.auth.models import User
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.future_story.schemas import (
    FutureStoryDraftIn,
    FutureStoryDraftPublic,
    FutureStoryPublic,
    FutureStoryQuestion,
    FutureStoryUpdateIn,
)
from app.core.future_story.services import (
    get_latest_story,
    upsert_draft_answer,
    update_story_horizon,
)
from app.response import StandardResponse, make_success_response
from app.response.response import APIError
from mechtaai_bg_worker.celery_app import celery_app


router = APIRouter(prefix="/future-story", tags=["future-story"])


@router.get(
    "/questions",
    response_model=StandardResponse,
    summary="Получить вопросы для интервью",
)
def future_story_questions_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    _ = user
    areas = (
        db.query(Area)
        .filter(Area.is_active.is_(True))
        .order_by(asc(Area.order_index), asc(Area.id))
        .all()
    )
    questions: List[Dict[str, str]] = []
    for area in areas:
        questions.append(
            {
                "area_id": area.id,
                "question": f"Как выглядит ваша жизнь в сфере «{area.title}» через 5 лет?",
            }
        )
    payload = [FutureStoryQuestion.model_validate(q).model_dump() for q in questions]
    return make_success_response(result=payload)


@router.post(
    "/draft",
    response_model=StandardResponse,
    summary="Сохранить ответ (draft)",
)
def future_story_draft_view(
    payload: FutureStoryDraftIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    draft = upsert_draft_answer(
        db=db,
        user_id=user.id,
        area_id=payload.area_id,
        question=payload.question,
        answer=payload.answer,
    )
    return make_success_response(result=FutureStoryDraftPublic.from_orm(draft))


@router.post(
    "/generate",
    response_model=StandardResponse,
    summary="Сгенерировать историю",
)
def future_story_generate_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    _ = db
    task = celery_app.send_task("future_story.generate", args=[str(user.id)])
    timeout_seconds = settings.ai_proxy_timeout_seconds + 30
    try:
        result = task.get(timeout=timeout_seconds)
    except CeleryTimeoutError:
        raise APIError(
            code="FUTURE_STORY_AI_TIMEOUT",
            http_code=504,
            message="Future story generation timed out.",
        )

    if not result or not result.get("ok"):
        error = (result or {}).get("error") or {}
        raise APIError(
            code=error.get("code", "FUTURE_STORY_AI_FAILED"),
            http_code=error.get("http_code", 500),
            message=error.get("message", "Future story generation failed."),
        )

    story = FutureStoryPublic.model_validate(result["story"]).model_dump(mode="json")
    return make_success_response(result=story)


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить текущую историю",
)
def future_story_get_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    story = get_latest_story(db, user.id)
    if story is None:
        return make_success_response(result=None)
    payload = FutureStoryPublic.model_validate(story).model_dump(mode="json")
    return make_success_response(result=payload)


@router.put(
    "",
    response_model=StandardResponse,
    summary="Обновить историю вручную",
)
def future_story_update_view(
    payload: FutureStoryUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    story = update_story_horizon(
        db=db,
        user_id=user.id,
        horizon=payload.horizon,
        full_text=payload.full_text,
        by_area=[item.model_dump() for item in payload.by_area],
    )
    result = FutureStoryPublic.model_validate(story).model_dump(mode="json")
    return make_success_response(result=result)


__all__ = ["router"]
