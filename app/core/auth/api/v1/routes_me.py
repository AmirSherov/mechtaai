from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from redis import Redis
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.auth.schemas import ChangePasswordRequest, UserPublic, UserUpdate
from app.core.auth.services import logout_all_sessions, validate_password_strength
from app.core.dependencies import get_current_user, get_db
from app.core.security import hash_password, verify_password
from app.response import StandardResponse, make_success_response
from app.response.response import APIError
from app.utils.redis_client import get_redis


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter(
    prefix="/me",
    tags=["auth"],
)


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить текущего пользователя",
)
def get_me(
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Возвращает информацию о текущем пользователе.
    Результат кешируется в Redis на 60 секунд.
    """
    cache_key = f"me:user:{user.id}"

    redis: Redis | None = None
    try:
        redis = get_redis()
        cached = redis.get(cache_key)
        if cached is not None:
            logger.info("me cache hit (key=%s)", cache_key)
            data = json.loads(cached)
            return make_success_response(result=data)
        logger.info("me cache miss (key=%s)", cache_key)
    except Exception as exc:
        logger.warning("me cache error: %r", exc)
        redis = None

    result_data: Dict[str, Any] = {
        "user": UserPublic.from_orm(user).model_dump(),
    }

    if redis is not None:
        try:
            payload = jsonable_encoder(result_data)
            redis.setex(cache_key, 60, json.dumps(payload))
            logger.info("me cache set (key=%s, ttl=%s)", cache_key, 60)
        except Exception as exc:
            logger.warning("me cache set error: %r", exc)

    return make_success_response(result=result_data)


@router.put(
    "",
    response_model=StandardResponse,
    summary="Обновить профиль текущего пользователя",
)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Обновляет публичные поля профиля и сбрасывает кеш /me для этого пользователя.
    """
    data = payload.dict(exclude_unset=True)

    for field, value in data.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    result_data: Dict[str, Any] = {
        "user": UserPublic.from_orm(user).model_dump(),
    }

    cache_key = f"me:user:{user.id}"
    try:
        redis = get_redis()
        redis.delete(cache_key)
        payload = jsonable_encoder(result_data)
        redis.setex(cache_key, 60, json.dumps(payload))
        logger.info("me cache refreshed after update (key=%s)", cache_key)
    except Exception as exc:
        logger.warning("me cache update error: %r", exc)

    return make_success_response(result=result_data)


@router.put(
    "/password",
    response_model=StandardResponse,
    summary="Сменить пароль текущего пользователя",
)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Меняет пароль пользователя, инвалидирует все его сессии
    и сбрасывает кеш /me.
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise APIError(
            code="AUTH_INVALID_CURRENT_PASSWORD",
            http_code=400,
            message="Текущий пароль указан неверно",
        )

    validate_password_strength(payload.new_password)

    user.password_hash = hash_password(payload.new_password)
    db.add(user)

    logout_all_sessions(db, user_id=user.id)
    db.commit()

    cache_key = f"me:user:{user.id}"
    try:
        redis = get_redis()
        redis.delete(cache_key)
        logger.info(
            "me cache invalidated after password change (key=%s)", cache_key
        )
    except Exception as exc:
        logger.warning("me cache invalidation error: %r", exc)

    return make_success_response(result={"success": True})


__all__ = ["router"]
