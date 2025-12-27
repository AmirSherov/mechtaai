from __future__ import annotations

from datetime import date, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.plan_steps.models import Step
from app.core.rituals.models import JournalEntry, WeeklyReview
from app.response.response import APIError


def get_today_status(db: Session, user_id: UUID, today: date) -> dict:
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id, JournalEntry.date == today)
        .all()
    )
    morning_done = any(e.type == "morning" for e in entries)
    evening_done = any(e.type == "evening" for e in entries)
    return {
        "date": today,
        "morning_done": morning_done,
        "evening_done": evening_done,
    }


def create_journal_entry(
    db: Session,
    user_id: UUID,
    today: date,
    entry_type: str,
    answers: dict,
    mood_score: int | None,
    energy_score: int | None,
) -> JournalEntry:
    exists = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user_id,
            JournalEntry.date == today,
            JournalEntry.type == entry_type,
        )
        .first()
    )
    if exists is not None:
        raise APIError(
            code="RITUALS_ALREADY_COMPLETED",
            http_code=409,
            message="Ритуал уже выполнен сегодня.",
        )

    entry = JournalEntry(
        user_id=user_id,
        date=today,
        type=entry_type,
        answers=answers,
        mood_score=mood_score,
        energy_score=energy_score,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_week_bounds(ref_date: date) -> tuple[date, date]:
    week_start = ref_date - timedelta(days=ref_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_weekly_steps(
    db: Session,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> tuple[List[Step], List[Step]]:
    steps = (
        db.query(Step)
        .filter(
            Step.user_id == user_id,
            Step.planned_date.isnot(None),
            Step.planned_date >= week_start,
            Step.planned_date <= week_end,
        )
        .all()
    )
    completed = [s for s in steps if s.status == "done"]
    failed = [s for s in steps if s.status in {"planned", "in_progress", "skipped"}]
    return completed, failed


def get_week_mood_avg(
    db: Session,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> float | None:
    entries = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.user_id == user_id,
            JournalEntry.date >= week_start,
            JournalEntry.date <= week_end,
            JournalEntry.mood_score.isnot(None),
        )
        .all()
    )
    if not entries:
        return None
    total = sum(e.mood_score or 0 for e in entries)
    return round(total / len(entries), 2)


def create_weekly_review(
    db: Session,
    user_id: UUID,
    week_start: date,
    week_end: date,
    completed_steps: list,
    failed_steps: list,
    user_reflection: str,
    ai_analysis: dict,
) -> WeeklyReview:
    review = WeeklyReview(
        user_id=user_id,
        week_start=week_start,
        week_end=week_end,
        completed_steps=completed_steps,
        failed_steps=failed_steps,
        user_reflection=user_reflection,
        ai_analysis=ai_analysis,
        status="in_progress",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def create_empty_weekly_review(
    db: Session,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> WeeklyReview:
    review = WeeklyReview(
        user_id=user_id,
        week_start=week_start,
        week_end=week_end,
        completed_steps=[],
        failed_steps=[],
        status="in_progress",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_latest_weekly_review(db: Session, user_id: UUID) -> WeeklyReview | None:
    return (
        db.query(WeeklyReview)
        .filter(WeeklyReview.user_id == user_id)
        .order_by(desc(WeeklyReview.created_at))
        .first()
    )


def run_auto_archive(db: Session, review: WeeklyReview) -> None:
    week_start = review.week_start
    week_end = review.week_end
    steps = (
        db.query(Step)
        .filter(
            Step.user_id == review.user_id,
            Step.planned_date.isnot(None),
            Step.planned_date >= week_start,
            Step.planned_date <= week_end,
            Step.status != "done",
        )
        .all()
    )
    for step in steps:
        step.planned_date = None
        step.status = "planned"

    review.status = "auto_archived"
    db.add(review)
    if steps:
        db.add_all(steps)
    db.commit()


def get_plan_suggestion(
    db: Session,
    user_id: UUID,
    limit: int = 20,
) -> List[Step]:
    steps = (
        db.query(Step)
        .filter(
            Step.user_id == user_id,
            Step.status == "planned",
            Step.planned_date.is_(None),
            Step.level.in_(["quarter", "month"]),
        )
        .order_by(asc(Step.created_at))
        .limit(limit)
        .all()
    )
    return steps


def commit_week_plan(
    db: Session,
    user_id: UUID,
    next_week_step_ids: list[UUID],
    week_start: date,
) -> List[Step]:
    next_week_end = week_start + timedelta(days=6)
    steps = (
        db.query(Step)
        .filter(Step.user_id == user_id, Step.id.in_(next_week_step_ids))
        .all()
    )
    if not steps:
        raise APIError(
            code="RITUALS_STEPS_NOT_FOUND",
            http_code=404,
            message="Шаги не найдены.",
        )

    for step in steps:
        if step.planned_date is None:
            step.planned_date = next_week_end
        step.status = "planned"

    db.add_all(steps)
    db.commit()
    for step in steps:
        db.refresh(step)
    return steps


def get_today_status_with_interception(
    db: Session,
    user_id: UUID,
    today: date,
) -> dict:
    base = get_today_status(db, user_id, today)
    latest = get_latest_weekly_review(db, user_id)
    if latest is None:
        return {**base, "interception": None}

    if latest.status in {"completed", "auto_archived"}:
        current_start, current_end = get_week_bounds(today)
        if latest.week_start < current_start:
            create_empty_weekly_review(db, user_id, current_start, current_end)
        return {**base, "interception": None}

    days_late = (today - latest.week_end).days
    if days_late <= 0:
        return {**base, "interception": None}

    if days_late <= 3:
        return {
            **base,
            "interception": {
                "active": True,
                "type": "force_review",
                "week_review_id": str(latest.id),
            },
        }

    run_auto_archive(db, latest)
    current_start, current_end = get_week_bounds(today)
    create_empty_weekly_review(db, user_id, current_start, current_end)
    return {
        **base,
        "interception": {
            "active": True,
            "type": "fresh_start",
            "week_review_id": None,
        },
    }


__all__ = [
    "get_today_status",
    "get_today_status_with_interception",
    "create_journal_entry",
    "get_week_bounds",
    "get_weekly_steps",
    "get_week_mood_avg",
    "create_weekly_review",
    "create_empty_weekly_review",
    "get_latest_weekly_review",
    "get_plan_suggestion",
    "commit_week_plan",
    "run_auto_archive",
]
