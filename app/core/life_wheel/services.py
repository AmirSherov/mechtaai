from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.areas.models import Area
from app.core.life_wheel.models import LifeWheel
from app.core.life_wheel.schemas import LifeWheelCreate
from app.response.response import APIError


def _fetch_active_area_ids(db: Session) -> List[str]:
    areas = db.query(Area.id).filter(Area.is_active.is_(True)).order_by(
        asc(Area.order_index),
        asc(Area.id),
    )
    return [a.id for a in areas]


def validate_scores(
    db: Session,
    scores: Dict[str, int],
) -> None:
    if not scores:
        raise APIError(
            code="LIFE_WHEEL_EMPTY_SCORES",
            http_code=400,
            message="Нужно передать хотя бы одну оценку по сферам.",
        )

    active_area_ids = set(_fetch_active_area_ids(db))
    invalid_ids = [k for k in scores.keys() if k not in active_area_ids]
    if invalid_ids:
        raise APIError(
            code="LIFE_WHEEL_INVALID_AREA_ID",
            http_code=400,
            message="Некоторые коды сфер не существуют или не активны.",
            fields={"area_ids": invalid_ids},
        )


def create_life_wheel(
    db: Session,
    user_id,
    payload: LifeWheelCreate,
) -> LifeWheel:
    validate_scores(db, payload.scores)

    life_wheel = LifeWheel(
        user_id=user_id,
        scores=dict(payload.scores),
        note=payload.note,
    )
    db.add(life_wheel)
    db.commit()
    db.refresh(life_wheel)
    return life_wheel


def get_latest_life_wheel(
    db: Session,
    user_id,
) -> LifeWheel | None:
    return (
        db.query(LifeWheel)
        .filter(LifeWheel.user_id == user_id)
        .order_by(desc(LifeWheel.created_at))
        .first()
    )


def get_life_wheels_page(
    db: Session,
    user_id,
    page: int,
    page_size: int,
) -> Tuple[List[LifeWheel], int]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10

    query = db.query(LifeWheel).filter(LifeWheel.user_id == user_id)
    total = query.count()

    items = (
        query.order_by(desc(LifeWheel.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


__all__ = [
    "create_life_wheel",
    "get_latest_life_wheel",
    "get_life_wheels_page",
]

