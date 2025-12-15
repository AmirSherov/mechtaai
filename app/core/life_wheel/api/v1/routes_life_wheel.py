from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.core.life_wheel.schemas import LifeWheelCreate, LifeWheelPublic
from app.core.life_wheel.services import (
    create_life_wheel,
    get_latest_life_wheel,
    get_life_wheels_page,
)
from app.response import Pagination, StandardResponse, make_success_response


router = APIRouter(prefix="/life_wheel", tags=["life_wheel"])


@router.post(
    "",
    response_model=StandardResponse,
    summary="Создать новый замер колеса жизни",
)
def create_life_wheel_view(
    payload: LifeWheelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    life_wheel = create_life_wheel(db, user.id, payload)
    result = LifeWheelPublic.from_orm(life_wheel)
    return make_success_response(result=result)


@router.get(
    "/latest",
    response_model=StandardResponse,
    summary="Получить последний замер колеса жизни текущего пользователя",
)
def get_latest_life_wheel_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    life_wheel = get_latest_life_wheel(db, user.id)
    if life_wheel is None:
        return make_success_response(result=None)

    result = LifeWheelPublic.from_orm(life_wheel)
    return make_success_response(result=result)


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить историю замеров колеса жизни текущего пользователя",
)
def list_life_wheels_view(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    items, total = get_life_wheels_page(
        db=db,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )

    result_items: List[Dict[str, Any]] = [
        LifeWheelPublic.from_orm(i).model_dump() for i in items
    ]

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1
    pagination = Pagination(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    payload: Dict[str, Any] = {
        "items": result_items,
    }
    return make_success_response(
        result=jsonable_encoder(payload),
        pagination=pagination,
    )

