from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.wants.models import WantsRaw, WantsRawChunk
from app.response.response import APIError


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_stop_word(text: str) -> bool:
    t = text.strip().casefold()
    return t in {"стоп", "stop"}


def _ensure_draft_mutable(wants_raw: WantsRaw) -> None:
    if wants_raw.status != "draft":
        raise APIError(
            code="WANTS_RAW_IMMUTABLE",
            http_code=409,
            message="Нельзя изменять completed wants_raw.",
        )


def get_draft(db: Session, user_id: UUID) -> WantsRaw | None:
    return (
        db.query(WantsRaw)
        .filter(
            WantsRaw.user_id == user_id,
            WantsRaw.status == "draft",
        )
        .order_by(desc(WantsRaw.updated_at))
        .first()
    )


def get_or_create_draft(db: Session, user_id: UUID) -> WantsRaw:
    existing = get_draft(db, user_id)
    if existing is not None:
        return existing

    draft = WantsRaw(user_id=user_id, status="draft")
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def get_completed_by_id(
    db: Session, user_id: UUID, raw_id: UUID
) -> WantsRaw | None:
    return (
        db.query(WantsRaw)
        .filter(
            WantsRaw.user_id == user_id,
            WantsRaw.id == raw_id,
            WantsRaw.status == "completed",
        )
        .first()
    )


def start_stream(db: Session, user_id: UUID) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    if wants_raw.stream_started_at is None:
        wants_raw.stream_started_at = _now_utc()

    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def append_stream_text(
    db: Session, user_id: UUID, text: str
) -> Tuple[WantsRaw, bool]:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    if wants_raw.stream_started_at is None:
        wants_raw.stream_started_at = _now_utc()

    if _is_stop_word(text):
        if wants_raw.stream_completed_at is None:
            wants_raw.stream_completed_at = _now_utc()
        db.add(wants_raw)
        db.commit()
        db.refresh(wants_raw)
        return wants_raw, True

    current = (wants_raw.raw_wants_stream or "").rstrip()
    wants_raw.raw_wants_stream = f"{current}\n{text}".lstrip() if current else text

    chunk = WantsRawChunk(
        wants_raw_id=wants_raw.id,
        exercise="stream",
        text=text,
    )
    db.add(chunk)
    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw, False


def finish_stream(db: Session, user_id: UUID) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    if wants_raw.stream_completed_at is None:
        wants_raw.stream_completed_at = _now_utc()

    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def set_future_me(db: Session, user_id: UUID, text: str) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)
    wants_raw.raw_future_me = text
    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def append_future_me_text(db: Session, user_id: UUID, text: str) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    current = (wants_raw.raw_future_me or "").rstrip()
    wants_raw.raw_future_me = f"{current}\n{text}".lstrip() if current else text

    chunk = WantsRawChunk(
        wants_raw_id=wants_raw.id,
        exercise="future_me",
        text=text,
    )
    db.add(chunk)
    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def finish_future_me(db: Session, user_id: UUID) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    if wants_raw.future_me_completed_at is None:
        wants_raw.future_me_completed_at = _now_utc()

    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def update_reverse(
    db: Session,
    user_id: UUID,
    payload: Dict[str, Any],
) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    if "raw_envy" in payload and payload["raw_envy"] is not None:
        wants_raw.raw_envy = payload["raw_envy"]
    if "raw_regrets" in payload and payload["raw_regrets"] is not None:
        wants_raw.raw_regrets = payload["raw_regrets"]
    if "raw_what_to_do_5y" in payload and payload["raw_what_to_do_5y"] is not None:
        wants_raw.raw_what_to_do_5y = payload["raw_what_to_do_5y"]

    if (
        (wants_raw.raw_envy or "").strip()
        and (wants_raw.raw_regrets or "").strip()
        and (wants_raw.raw_what_to_do_5y or "").strip()
    ):
        if wants_raw.reverse_completed_at is None:
            wants_raw.reverse_completed_at = _now_utc()

    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def get_progress(db: Session, user_id: UUID) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)
    return wants_raw


def _validate_complete(wants_raw: WantsRaw) -> None:
    missing_fields: Dict[str, List[str]] = {}

    if wants_raw.stream_completed_at is None or not (wants_raw.raw_wants_stream or "").strip():
        missing_fields["stream"] = ["Заполните поток и завершите упражнение."]
    if wants_raw.future_me_completed_at is None or not (wants_raw.raw_future_me or "").strip():
        missing_fields["future_me"] = ["Заполните упражнение 'мне 40' и завершите его."]
    if wants_raw.reverse_completed_at is None:
        missing_fields["reverse"] = ["Ответьте на 3 reverse-вопроса."]
    else:
        if not (wants_raw.raw_envy or "").strip():
            missing_fields["raw_envy"] = ["Поле обязательно."]
        if not (wants_raw.raw_regrets or "").strip():
            missing_fields["raw_regrets"] = ["Поле обязательно."]
        if not (wants_raw.raw_what_to_do_5y or "").strip():
            missing_fields["raw_what_to_do_5y"] = ["Поле обязательно."]

    if missing_fields:
        raise APIError(
            code="WANTS_RAW_NOT_READY",
            http_code=422,
            message="wants_raw нельзя завершить: не все поля заполнены.",
            fields=missing_fields,
        )


def complete_wants(db: Session, user_id: UUID) -> WantsRaw:
    wants_raw = get_or_create_draft(db, user_id)
    _ensure_draft_mutable(wants_raw)

    _validate_complete(wants_raw)

    wants_raw.status = "completed"
    wants_raw.completed_at = _now_utc()

    db.add(wants_raw)
    db.commit()
    db.refresh(wants_raw)
    return wants_raw


def get_history_page(
    db: Session,
    user_id: UUID,
    page: int,
    page_size: int,
) -> Tuple[List[WantsRaw], int]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    query = (
        db.query(WantsRaw)
        .filter(
            WantsRaw.user_id == user_id,
            WantsRaw.status == "completed",
        )
    )
    total = query.count()

    items = (
        query.order_by(desc(WantsRaw.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


__all__ = [
    "get_draft",
    "get_or_create_draft",
    "get_completed_by_id",
    "start_stream",
    "append_stream_text",
    "finish_stream",
    "set_future_me",
    "append_future_me_text",
    "finish_future_me",
    "update_reverse",
    "get_progress",
    "complete_wants",
    "get_history_page",
]

