from __future__ import annotations

import json
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from redis import Redis
from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.core.areas.models import Area
from app.core.areas.schemas import AreaCreate, AreaPublic, AreaUpdate
from app.core.areas.services import ensure_default_areas
from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.utils.redis_client import get_redis
from app.response import StandardResponse, make_success_response
from app.response.response import APIError


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter(prefix="/areas", tags=["areas"])


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить список сфер жизни (areas)",
)
def list_areas(
    include_inactive: bool = Query(
        default=False,
        description="Включить ли неактивные сферы",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Возвращает список сфер жизни, отсортированный по order_index и id.
    Требует аутентифицированного пользователя.
    """
    cache_key = f"areas:list:{int(include_inactive)}"

    redis: Redis | None = None
    try:
        redis = get_redis()
        cached = redis.get(cache_key)
        if cached is not None:
            logger.info("areas cache hit (key=%s)", cache_key)
            data = json.loads(cached)
            return make_success_response(result=data)
        logger.info("areas cache miss (key=%s)", cache_key)
    except Exception as exc:
        logger.warning("areas cache error: %r", exc)
        redis = None

    ensure_default_areas(db)

    query = db.query(Area)
    if not include_inactive:
        query = query.filter(Area.is_active.is_(True))

    areas: List[Area] = query.order_by(
        asc(Area.order_index),
        asc(Area.id),
    ).all()

    result_items = [
        AreaPublic.from_orm(a).model_dump() for a in areas
    ]
    result: Dict[str, List[Dict]] = {"items": result_items}

    if redis is not None:
        try:
            payload = jsonable_encoder(result)
            redis.setex(cache_key, 120, json.dumps(payload))
            logger.info("areas cache set (key=%s, ttl=%s)", cache_key, 120)
        except Exception as exc:
            logger.warning("areas cache set error: %r", exc)

    return make_success_response(result=result)


@router.get(
    "/{area_id}",
    response_model=StandardResponse,
    summary="Получить одну сферу по id",
)
def get_area(
    area_id: str,
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Возвращает одну область по её id.
    Доступно без авторизации.
    """
    cache_key = f"areas:item:{area_id}"

    redis: Redis | None = None
    try:
        redis = get_redis()
        cached = redis.get(cache_key)
        if cached is not None:
            logger.info("areas item cache hit (key=%s)", cache_key)
            data = json.loads(cached)
            return make_success_response(result=data)
        logger.info("areas item cache miss (key=%s)", cache_key)
    except Exception as exc:
        logger.warning("areas item cache error: %r", exc)
        redis = None

    area = db.query(Area).filter(Area.id == area_id).first()
    if area is None:
        raise APIError(
            code="AREA_NOT_FOUND",
            http_code=404,
            message="Сфера с таким id не найдена",
            fields={"area_id": ["Некорректный идентификатор области"]},
        )

    area_data = AreaPublic.from_orm(area).model_dump()

    if redis is not None:
        try:
            payload = jsonable_encoder(area_data)
            redis.setex(cache_key, 120, json.dumps(payload))
            logger.info(
                "areas item cache set (key=%s, ttl=%s)", cache_key, 120
            )
        except Exception as exc:
            logger.warning("areas item cache set error: %r", exc)

    return make_success_response(result=area_data)


@router.post(
    "",
    response_model=StandardResponse,
    summary="Создать новую сферу (admin only)",
)
def create_area(
    payload: AreaCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Создаёт новую область. Доступно только администратору.
    """
    if not user.is_superuser:
        raise APIError(
            code="AUTH_FORBIDDEN",
            http_code=403,
            message="Требуются права администратора",
        )

    existing = db.query(Area).filter(Area.id == payload.id).first()
    if existing is not None:
        raise APIError(
            code="AREA_ALREADY_EXISTS",
            http_code=400,
            message="Сфера с таким id уже существует",
            fields={"id": ["Значение должно быть уникальным"]},
        )

    area = Area(
        id=payload.id,
        title=payload.title,
        description=payload.description,
        order_index=payload.order_index,
        is_active=payload.is_active,
    )
    db.add(area)
    db.commit()
    db.refresh(area)

    # invalidate caches
    try:
        redis = get_redis()
        redis.delete(
            f"areas:item:{area.id}",
            "areas:list:0",
            "areas:list:1",
        )
        logger.info("areas cache invalidated after create (id=%s)", area.id)
    except Exception as exc:
        logger.warning("areas cache invalidation error (create): %r", exc)

    return make_success_response(result=AreaPublic.from_orm(area))


@router.put(
    "/{area_id}",
    response_model=StandardResponse,
    summary="Обновить сферу (admin only)",
)
def update_area(
    area_id: str,
    payload: AreaUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Обновляет существующую область. Доступно только администратору.
    """
    if not user.is_superuser:
        raise APIError(
            code="AUTH_FORBIDDEN",
            http_code=403,
            message="Требуются права администратора",
        )

    area = db.query(Area).filter(Area.id == area_id).first()
    if area is None:
        raise APIError(
            code="AREA_NOT_FOUND",
            http_code=404,
            message="Сфера с таким id не найдена",
            fields={"area_id": ["Некорректный идентификатор области"]},
        )

    if payload.title is not None:
        area.title = payload.title
    if payload.description is not None:
        area.description = payload.description
    if payload.order_index is not None:
        area.order_index = payload.order_index
    if payload.is_active is not None:
        area.is_active = payload.is_active

    db.add(area)
    db.commit()
    db.refresh(area)

    # invalidate caches
    try:
        redis = get_redis()
        redis.delete(
            f"areas:item:{area.id}",
            "areas:list:0",
            "areas:list:1",
        )
        logger.info("areas cache invalidated after update (id=%s)", area.id)
    except Exception as exc:
        logger.warning("areas cache invalidation error (update): %r", exc)

    return make_success_response(result=AreaPublic.from_orm(area))


@router.delete(
    "/{area_id}",
    response_model=StandardResponse,
    summary="Деактивировать сферу (admin only)",
)
def delete_area(
    area_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Логическое удаление области: помечаем is_active = False.
    Физическое удаление не делаем, чтобы не ломать ссылки.
    Доступно только администратору.
    """
    if not user.is_superuser:
        raise APIError(
            code="AUTH_FORBIDDEN",
            http_code=403,
            message="Требуются права администратора",
        )

    area = db.query(Area).filter(Area.id == area_id).first()
    if area is None:
        raise APIError(
            code="AREA_NOT_FOUND",
            http_code=404,
            message="Сфера с таким id не найдена",
            fields={"area_id": ["Некорректный идентификатор области"]},
        )

    area.is_active = False
    db.add(area)
    db.commit()
    db.refresh(area)

    # invalidate caches
    try:
        redis = get_redis()
        redis.delete(
            f"areas:item:{area.id}",
            "areas:list:0",
            "areas:list:1",
        )
        logger.info("areas cache invalidated after delete (id=%s)", area.id)
    except Exception as exc:
        logger.warning("areas cache invalidation error (delete): %r", exc)

    return make_success_response(result=AreaPublic.from_orm(area))


__all__ = ["router"]
