from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.future_story.models import FutureStory, FutureStoryDraft
from app.response.response import APIError


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_draft(db: Session, user_id: UUID) -> FutureStoryDraft:
    draft = (
        db.query(FutureStoryDraft)
        .filter(
            FutureStoryDraft.user_id == user_id,
            FutureStoryDraft.status == "in_progress",
        )
        .order_by(desc(FutureStoryDraft.updated_at))
        .first()
    )
    if draft is not None:
        return draft

    draft = FutureStoryDraft(
        user_id=user_id,
        answers=[],
        status="in_progress",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def upsert_draft_answer(
    db: Session,
    user_id: UUID,
    area_id: str,
    question: str,
    answer: str,
) -> FutureStoryDraft:
    draft = get_or_create_draft(db, user_id)
    answers: List[Dict[str, Any]] = list(draft.answers or [])

    updated = False
    for item in answers:
        if item.get("area_id") == area_id and item.get("question") == question:
            item["answer"] = answer
            updated = True
            break

    if not updated:
        answers.append(
            {
                "area_id": area_id,
                "question": question,
                "answer": answer,
            }
        )

    draft.answers = answers
    draft.updated_at = _now_utc()
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def mark_draft_completed(db: Session, draft: FutureStoryDraft) -> FutureStoryDraft:
    draft.status = "completed"
    draft.updated_at = _now_utc()
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def get_latest_draft(db: Session, user_id: UUID) -> FutureStoryDraft | None:
    return (
        db.query(FutureStoryDraft)
        .filter(FutureStoryDraft.user_id == user_id)
        .order_by(desc(FutureStoryDraft.updated_at))
        .first()
    )


def create_future_story(
    db: Session,
    user_id: UUID,
    horizon_3y: Dict[str, Any],
    horizon_5y: Dict[str, Any],
    key_images: List[Dict[str, Any]],
    validation_notes: str | None,
) -> FutureStory:
    story = FutureStory(
        user_id=user_id,
        horizon_3y=horizon_3y,
        horizon_5y=horizon_5y,
        key_images=key_images,
        validation_notes=validation_notes,
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def get_latest_story(db: Session, user_id: UUID) -> FutureStory | None:
    return (
        db.query(FutureStory)
        .filter(FutureStory.user_id == user_id)
        .order_by(desc(FutureStory.created_at))
        .first()
    )


def update_story_horizon(
    db: Session,
    user_id: UUID,
    horizon: str,
    full_text: str,
    by_area: List[Dict[str, Any]],
) -> FutureStory:
    story = get_latest_story(db, user_id)
    if story is None:
        raise APIError(
            code="FUTURE_STORY_NOT_FOUND",
            http_code=404,
            message="Future story не найден.",
        )

    payload = {"full_text": full_text, "by_area": by_area}
    if horizon == "3y":
        story.horizon_3y = payload
    elif horizon == "5y":
        story.horizon_5y = payload
    else:
        raise APIError(
            code="FUTURE_STORY_INVALID_HORIZON",
            http_code=400,
            message="Недопустимое значение horizon.",
        )

    db.add(story)
    db.commit()
    db.refresh(story)
    return story


__all__ = [
    "get_or_create_draft",
    "upsert_draft_answer",
    "mark_draft_completed",
    "get_latest_draft",
    "create_future_story",
    "get_latest_story",
    "update_story_horizon",
]
