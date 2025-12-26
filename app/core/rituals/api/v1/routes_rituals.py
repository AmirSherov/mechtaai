from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List
from uuid import UUID

from celery.exceptions import TimeoutError as CeleryTimeoutError
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.rituals.schemas import (
    JournalEntryIn,
    JournalEntryPublic,
    RitualsTodayStatus,
    StepPublic,
    WeeklyAnalyzeIn,
    WeeklyCommitIn,
    WeeklyReviewPublic,
)
from app.core.rituals.services import (
    commit_week_plan,
    create_journal_entry,
    create_weekly_review,
    get_plan_suggestion,
    get_today_status_with_interception,
    get_week_bounds,
    get_week_mood_avg,
    get_weekly_steps,
)
from app.core.gamification.services import (
    ActionType,
    award_action,
    build_gamification_event,
)
from app.response import StandardResponse, make_success_response
from app.response.response import APIError
from mechtaai_bg_worker.celery_app import celery_app


router = APIRouter(prefix="/rituals", tags=["rituals"])


@router.get(
    "/today",
    response_model=StandardResponse,
    summary="Статус ритуалов на сегодня",
)
def rituals_today_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    today = date.today()
    status = get_today_status_with_interception(db, user.id, today)
    payload = RitualsTodayStatus.model_validate(status).model_dump(mode="json")
    return make_success_response(result=payload)


@router.post(
    "/entry",
    response_model=StandardResponse,
    summary="Сохранить ритуал",
)
def rituals_entry_view(
    payload: JournalEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    today = date.today()
    entry = create_journal_entry(
        db=db,
        user_id=user.id,
        today=today,
        entry_type=payload.type,
        answers=payload.answers,
        mood_score=payload.mood_score,
        energy_score=payload.energy_score,
    )
    action_type = (
        ActionType.DAILY_RITUAL_MORNING
        if payload.type == "morning"
        else ActionType.DAILY_RITUAL_EVENING
    )
    award_result = award_action(db, user.id, action_type)
    result = JournalEntryPublic.model_validate(entry).model_dump(mode="json")
    result["gamification_event"] = build_gamification_event(
        action_type,
        award_result,
    )
    return make_success_response(result=result)


@router.post(
    "/weekly/analyze",
    response_model=StandardResponse,
    summary="Анализ недели (AI)",
)
def weekly_analyze_view(
    payload: WeeklyAnalyzeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    week_start, week_end = get_week_bounds(date.today() - timedelta(days=1))
    completed, failed = get_weekly_steps(db, user.id, week_start, week_end)
    mood_avg = get_week_mood_avg(db, user.id, week_start, week_end)
    week_dates = f"{week_start:%d.%m} - {week_end:%d.%m}"

    task = celery_app.send_task(
        "rituals.weekly_review",
        args=[
            str(user.id),
            {
                "week_dates": week_dates,
                "completed_steps": [
                    {"title": s.title, "area": None} for s in completed
                ],
                "failed_steps": [{"title": s.title, "area": None} for s in failed],
                "mood_avg": mood_avg,
                "user_reflection": payload.user_reflection,
            },
        ],
    )
    timeout_seconds = settings.ai_proxy_timeout_seconds + 30
    try:
        result = task.get(timeout=timeout_seconds)
    except CeleryTimeoutError:
        raise APIError(
            code="RITUALS_AI_TIMEOUT",
            http_code=504,
            message="Weekly review timed out.",
        )

    if not result or not result.get("ok"):
        error = (result or {}).get("error") or {}
        raise APIError(
            code=error.get("code", "RITUALS_AI_FAILED"),
            http_code=error.get("http_code", 500),
            message=error.get("message", "Weekly review failed."),
        )

    ai_analysis = result["analysis"]
    review = create_weekly_review(
        db=db,
        user_id=user.id,
        week_start=week_start,
        week_end=week_end,
        completed_steps=[str(s.id) for s in completed],
        failed_steps=[str(s.id) for s in failed],
        user_reflection=payload.user_reflection,
        ai_analysis=ai_analysis,
    )
    award_result = award_action(db, user.id, ActionType.WEEKLY_REVIEW_COMPLETE)
    response_payload = WeeklyReviewPublic.model_validate(review).model_dump(mode="json")
    response_payload["ai_analysis"] = ai_analysis
    response_payload["gamification_event"] = build_gamification_event(
        ActionType.WEEKLY_REVIEW_COMPLETE,
        award_result,
    )
    return make_success_response(result=response_payload)


@router.get(
    "/weekly/plan-suggestion",
    response_model=StandardResponse,
    summary="План на следующую неделю",
)
def weekly_plan_suggestion_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    steps = get_plan_suggestion(db, user.id)
    result = [StepPublic.model_validate(s).model_dump(mode="json") for s in steps]
    return make_success_response(result=result)


@router.post(
    "/weekly/commit",
    response_model=StandardResponse,
    summary="Зафиксировать план недели",
)
def weekly_commit_view(
    payload: WeeklyCommitIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    next_week_start = date.today() + timedelta(days=(7 - date.today().weekday()))
    steps = commit_week_plan(
        db=db,
        user_id=user.id,
        next_week_step_ids=payload.next_week_step_ids,
        week_start=next_week_start,
    )
    result = [StepPublic.model_validate(s).model_dump(mode="json") for s in steps]
    return make_success_response(result=result)


__all__ = ["router"]
