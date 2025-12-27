from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.auth.models import EmailVerificationToken, User, UserSession
from app.core.auth.schemas import (
    CheckEmailVerificationCodeRequest,
    LoginRequest,
    RefreshRequest,
    RequestPasswordReset,
    ResetPasswordConfirm,
    SendEmailVerificationRequest,
    SessionPublic,
    TelegramAuthRequest,
    TokenPair,
    UserCreate,
    UserPublic,
)
from app.core.auth.services import (
    MAX_VERIFICATION_ATTEMPTS,
    _utc_now,
    authenticate_user,
    authenticate_telegram_user,
    create_email_verification_token,
    create_session_and_tokens,
    create_user,
    logout_all_sessions,
    logout_session,
    refresh_tokens,
    request_password_reset,
    reset_password,
    send_email_verification,
)
from app.core.dependencies import get_current_user, get_db
from app.core.config import settings
from app.core.security import decode_token
from app.response import StandardResponse, make_success_response
from app.response.response import APIError


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=StandardResponse,
    summary="Регистрация нового пользователя",
    description=(
        "Создает пользователя с неактивным email, формирует токен и код "
        "подтверждения и инициирует отправку письма для верификации."
    ),
)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Принимает `UserCreate`, создает пользователя с `is_active = False` и
    запись в `email_verification_tokens`. Возвращает токен для подтверждения
    email и публичные данные пользователя.
    """
    user = create_user(db, payload)
    token = create_email_verification_token(db, user)
    db.commit()

    from app.core.notifications.email import schedule_email_verification

    schedule_email_verification(
        email=user.email,
        code=token.code,
        token=token.token,
    )

    result: Dict[str, Any] = {
        "verification_token": token.token,
        "user": UserPublic.from_orm(user),
    }
    return make_success_response(result=result)


@router.post(
    "/signin",
    response_model=StandardResponse,
    summary="Вход по email и паролю",
    description=(
        "Аутентифицирует пользователя по email и паролю, создает новую сессию "
        "и возвращает пару access/refresh токенов вместе с данными пользователя."
    ),
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> StandardResponse:
    """
    Принимает `LoginRequest`, проверяет учетные данные и активность пользователя,
    создает `UserSession` и возвращает `user` и `tokens`.
    """
    user = authenticate_user(db, payload)
    tokens = create_session_and_tokens(
        db,
        user,
        user_agent=user_agent,
    )
    db.commit()

    result: Dict[str, Any] = {
        "user": UserPublic.from_orm(user),
        "tokens": tokens,
    }
    return make_success_response(result=result)


@router.post(
    "/telegram",
    response_model=StandardResponse,
    summary="Telegram auth",
    description="Authenticate or register a user by Telegram data.",
)
def telegram_auth(
    payload: TelegramAuthRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
    bot_secret: str | None = Header(default=None, alias="X-Bot-Secret"),
) -> StandardResponse:
    if not bot_secret or bot_secret != settings.bot_secret_key:
        raise APIError(
            code="AUTH_TELEGRAM_FORBIDDEN",
            http_code=403,
            message="Access denied for non-bot request",
        )

    user = authenticate_telegram_user(db, payload)
    tokens = create_session_and_tokens(
        db,
        user,
        user_agent=user_agent,
    )
    db.commit()

    result: Dict[str, Any] = {
        "access_token": tokens.access_token,
        "token_type": tokens.token_type,
        "user": UserPublic.from_orm(user),
    }
    return make_success_response(result=result)


@router.post(
    "/refresh",
    response_model=StandardResponse,
    summary="Обновление access/refresh токенов",
    description=(
        "Обновляет пару токенов по валидному refresh-токену. "
        "Проверяет тип токена, связанную сессию и ее актуальность."
    ),
)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
) -> StandardResponse:
    """
    Принимает `RefreshRequest` с действительным refresh-токеном и возвращает новый `TokenPair`.
    """
    tokens: TokenPair = refresh_tokens(db, payload.refresh_token)
    db.commit()
    return make_success_response(result=tokens)


@router.post(
    "/logout",
    response_model=StandardResponse,
    summary="Выход из текущей сессии",
    description=(
        "Инвалидирует текущую пользовательскую сессию на основе access-токена. "
        "После этого все токены, связанные с этой сессией, становятся недействительными."
    ),
)
def logout(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> StandardResponse:
    if not authorization:
        raise APIError(
            code="AUTH_NOT_AUTHENTICATED",
            http_code=401,
            message="Требуется заголовок Authorization с Bearer токеном",
        )

    _, token = authorization.split(" ", 1)
    payload = decode_token(token)
    session_id_str = payload.get("session_id")
    try:
        session_id = uuid.UUID(session_id_str)
    except Exception:
        raise APIError(
            code="AUTH_INVALID_TOKEN_PAYLOAD",
            http_code=401,
            message="Некорректный payload токена",
        )

    logout_session(db, session_id=session_id, user_id=user.id)
    db.commit()
    return make_success_response(result={"success": True})


@router.post(
    "/logout-all",
    response_model=StandardResponse,
    summary="Выход из всех сессий пользователя",
    description=(
        "Инвалидирует все активные пользовательские сессии. "
        "Используется при глобальном выходе или смене пароля."
    ),
)
def logout_all(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    logout_all_sessions(db, user_id=user.id)
    db.commit()
    return make_success_response(result={"success": True})


@router.post(
    "/request-password-reset",
    response_model=StandardResponse,
)
def request_password_reset_endpoint(
    payload: RequestPasswordReset,
    db: Session = Depends(get_db),
) -> StandardResponse:
    request_password_reset(db, payload)
    db.commit()
    return make_success_response(result={"success": True})


@router.post(
    "/reset-password",
    response_model=StandardResponse,
)
def reset_password_endpoint(
    payload: ResetPasswordConfirm,
    db: Session = Depends(get_db),
) -> StandardResponse:
    reset_password(db, payload)
    db.commit()
    return make_success_response(result={"success": True})


@router.post(
    "/send-email-verification",
    response_model=StandardResponse,
    summary="Отправить код подтверждения email",
    description=(
        "Инициирует отправку кода подтверждения на указанный email для "
        "неподтвержденного пользователя и возвращает verification_token."
    ),
)
def send_email_verification_endpoint(
    payload: SendEmailVerificationRequest,
    db: Session = Depends(get_db),
) -> StandardResponse:
    token = send_email_verification(db, payload.email)
    db.commit()
    return make_success_response(result={"verification_token": token})


@router.post(
    "/check-email-verification-code",
    response_model=StandardResponse,
    summary="Подтвердить email по коду",
    description=(
        "Принимает verification_token и код, сверяет их с записью в "
        "`email_verification_tokens`, активирует пользователя и может вернуть токены."
    ),
)
def check_email_verification_code(
    payload: CheckEmailVerificationCodeRequest,
    db: Session = Depends(get_db),
) -> StandardResponse:
    token_row = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token == payload.verification_token)
        .first()
    )
    if token_row is None:
        raise APIError(
            code="AUTH_VERIFICATION_TOKEN_NOT_FOUND",
            http_code=400,
            message="Токен подтверждения не найден",
        )

    now = _utc_now()
    if token_row.used_at is not None or token_row.expires_at <= now:
        raise APIError(
            code="AUTH_VERIFICATION_TOKEN_EXPIRED",
            http_code=400,
            message="Токен подтверждения просрочен или уже использован",
        )

    if token_row.attempts >= MAX_VERIFICATION_ATTEMPTS:
        raise APIError(
            code="AUTH_VERIFICATION_ATTEMPTS_EXCEEDED",
            http_code=400,
            message="Превышено количество попыток ввода кода",
        )

    if token_row.code != payload.code:
        token_row.attempts += 1
        db.add(token_row)
        db.commit()
        raise APIError(
            code="AUTH_INVALID_VERIFICATION_CODE",
            http_code=400,
            message="Неверный код подтверждения",
        )

    user = db.query(User).filter(User.id == token_row.user_id).first()
    if user is None:
        raise APIError(
            code="AUTH_USER_NOT_FOUND",
            http_code=400,
            message="Пользователь не найден",
        )

    user.is_active = True
    token_row.used_at = now
    db.add(user)
    db.add(token_row)

    tokens = create_session_and_tokens(db, user)
    db.commit()

    result: Dict[str, Any] = {
        "user": UserPublic.from_orm(user),
        "tokens": tokens,
    }
    return make_success_response(result=result)


@router.get(
    "/sessions",
    response_model=StandardResponse,
)
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> StandardResponse:
    if not authorization:
        raise APIError(
            code="AUTH_NOT_AUTHENTICATED",
            http_code=401,
            message="Требуется заголовок Authorization с Bearer токеном",
        )

    _, token = authorization.split(" ", 1)
    payload = decode_token(token)
    current_session_id = payload.get("session_id")

    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .all()
    )

    result_sessions = []
    for s in sessions:
        is_current = str(s.id) == str(current_session_id)
        result_sessions.append(
            SessionPublic(
                id=s.id,
                user_agent=s.user_agent,
                ip_address=s.ip_address,
                device_name=s.device_name,
                created_at=s.created_at,
                expires_at=s.expires_at,
                revoked_at=s.revoked_at,
                is_current=is_current,
            )
        )

    return make_success_response(result={"sessions": result_sessions})


@router.delete(
    "/sessions/{session_id}",
    response_model=StandardResponse,
)
def revoke_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    logout_session(db, session_id=session_id, user_id=user.id)
    db.commit()
    return make_success_response(result={"success": True})


__all__ = ["router"]
