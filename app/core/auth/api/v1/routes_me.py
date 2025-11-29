from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.auth.schemas import ChangePasswordRequest, UserPublic, UserUpdate
from app.core.auth.services import logout_all_sessions, validate_password_strength
from app.core.dependencies import get_current_user, get_db
from app.core.security import hash_password, verify_password
from app.response import StandardResponse, make_success_response
from app.response.response import APIError


router = APIRouter(
    prefix="/me",
    tags=["auth"],
)


@router.get(
    "",
    response_model=StandardResponse,
    summary="Получить профиль текущего пользователя",
    description=(
        "Возвращает публичные данные авторизованного пользователя на основе access-токена."
    ),
)
def get_me(
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Возвращает `user` в формате `UserPublic` для текущего авторизованного пользователя.
    """
    result: Dict[str, Any] = {"user": UserPublic.from_orm(user)}
    return make_success_response(result=result)


@router.put(
    "",
    response_model=StandardResponse,
    summary="Обновить профиль текущего пользователя",
    description=(
        "Частично обновляет данные профиля (`first_name`, `last_name`, `time_zone` и т.д.) "
        "для текущего авторизованного пользователя."
    ),
)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Принимает `UserUpdate` и обновляет только переданные поля профиля текущего пользователя.
    """
    data = payload.dict(exclude_unset=True)

    for field, value in data.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)

    result: Dict[str, Any] = {"user": UserPublic.from_orm(user)}
    return make_success_response(result=result)


@router.put(
    "/password",
    response_model=StandardResponse,
    summary="Сменить пароль текущего пользователя",
    description=(
        "Меняет пароль для авторизованного пользователя после проверки текущего пароля. "
        "После смены пароля все активные сессии пользователя инвалидируются."
    ),
)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    """
    Принимает `ChangePasswordRequest` (`current_password`, `new_password`), проверяет текущий
    пароль и силу нового, затем обновляет пароль пользователя и завершает все его сессии.
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

    return make_success_response(result={"success": True})


__all__ = ["router"]

