from __future__ import annotations

import uuid
from typing import Generator

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.auth.models import User, UserSession
from app.core.security import decode_token
from app.database.session import SessionLocal
from app.response.response import APIError


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    if not authorization:
        raise APIError(
            code="AUTH_NOT_AUTHENTICATED",
            http_code=401,
            message="Требуется заголовок Authorization",
        )

    try:
        scheme, token = authorization.split(" ", 1)
    except ValueError:
        raise APIError(
            code="AUTH_INVALID_AUTH_HEADER",
            http_code=401,
            message="Некорректный заголовок Authorization",
        )

    if scheme.lower() != "bearer":
        raise APIError(
            code="AUTH_INVALID_AUTH_SCHEME",
            http_code=401,
            message="Ожидается схема авторизации Bearer",
        )

    try:
        payload = decode_token(token)
    except Exception:
        raise APIError(
            code="AUTH_INVALID_TOKEN",
            http_code=401,
            message="Невалидный или просроченный access-токен",
        )

    if payload.get("type") != "access":
        raise APIError(
            code="AUTH_INVALID_TOKEN_TYPE",
            http_code=401,
            message="Неверный тип токена",
        )

    user_id_str = payload.get("sub")
    session_id_str = payload.get("session_id")

    try:
        user_id = uuid.UUID(user_id_str)
        session_id = uuid.UUID(session_id_str)
    except Exception:
        raise APIError(
            code="AUTH_INVALID_TOKEN_PAYLOAD",
            http_code=401,
            message="Некорректный payload токена",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise APIError(
            code="AUTH_USER_NOT_FOUND",
            http_code=401,
            message="Пользователь не найден",
        )

    if not user.is_active:
        raise APIError(
            code="AUTH_USER_INACTIVE",
            http_code=403,
            message="Пользователь деактивирован",
        )

    session_obj = (
        db.query(UserSession)
        .filter(UserSession.id == session_id)
        .first()
    )
    if session_obj is None:
        raise APIError(
            code="AUTH_SESSION_NOT_FOUND",
            http_code=401,
            message="Сессия не найдена",
        )

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if session_obj.revoked_at is not None or session_obj.expires_at <= now:
        raise APIError(
            code="AUTH_SESSION_REVOKED",
            http_code=401,
            message="Сессия завершена",
        )

    return user


__all__ = ["get_db", "get_current_user"]
