from __future__ import annotations

from typing import Dict, Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.auth.schemas import (
    TelegramQRInitResponse,
    TelegramQRStatusResponse,
    TelegramQRConfirmRequest,
    TelegramQRExchangeRequest,
    TelegramQRExchangeResponse,
    UserPublic,
)
from app.core.auth.services import (
    create_qr_login_attempt,
    get_qr_login_status,
    confirm_qr_login,
    exchange_qr_secret_for_tokens,
)
from app.core.config import settings
from app.core.dependencies import get_db
from app.response import StandardResponse, make_success_response
from app.response.response import APIError


router = APIRouter(prefix="/auth/telegram/qr", tags=["auth"])


@router.post(
    "/init",
    response_model=StandardResponse,
    summary="Инициализация QR-логина через Telegram",
    description=(
        "Создает новую попытку входа через QR-код. Возвращает токен, "
        "данные для генерации QR-кода и deep-link на Telegram бота."
    ),
)
def init_qr_login(
    request: Request,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> StandardResponse:
    client_ip = request.client.host if request.client else None
    
    login_token, qr_code_data, deep_link, expires_in = create_qr_login_attempt(
        db,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    db.commit()
    
    result = TelegramQRInitResponse(
        login_token=login_token,
        qr_code_data=qr_code_data,
        deep_link=deep_link,
        expires_in_seconds=expires_in,
    )
    
    return make_success_response(result=result)


@router.get(
    "/status",
    response_model=StandardResponse,
    summary="Проверка статуса QR-логина",
    description=(
        "Polling эндпоинт. Возвращает текущий статус попытки входа. "
        "При статусе 'confirmed' возвращает one_time_secret для обмена на токены."
    ),
)
def check_qr_login_status(
    login_token: str,
    db: Session = Depends(get_db),
) -> StandardResponse:
    status, one_time_secret = get_qr_login_status(db, login_token)
    
    result = TelegramQRStatusResponse(
        status=status,
        one_time_secret=one_time_secret,
    )
    
    return make_success_response(result=result)


@router.post(
    "/confirm",
    response_model=StandardResponse,
    summary="Подтверждение QR-логина от бота",
    description=(
        "Internal API для Telegram бота. Подтверждает попытку входа "
        "и привязывает пользователя к login_token. Требует X-Bot-Secret."
    ),
)
def confirm_qr_login_endpoint(
    payload: TelegramQRConfirmRequest,
    db: Session = Depends(get_db),
    bot_secret: str | None = Header(default=None, alias="X-Bot-Secret"),
) -> StandardResponse:
    if not bot_secret or bot_secret != settings.bot_secret_key:
        raise APIError(
            code="AUTH_TELEGRAM_FORBIDDEN",
            http_code=403,
            message="Access denied for non-bot request",
        )
    
    confirm_qr_login(
        db,
        login_token=payload.login_token,
        telegram_id=payload.telegram_id,
        username=payload.username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        photo_url=payload.photo_url,
    )
    db.commit()
    
    return make_success_response(result={"success": True})


@router.post(
    "/exchange",
    response_model=StandardResponse,
    summary="Обмен one_time_secret на JWT токены",
    description=(
        "Обменивает одноразовый секрет на пару access/refresh токенов. "
        "Секрет можно использовать только один раз. Создает сессию пользователя."
    ),
)
def exchange_qr_secret(
    payload: TelegramQRExchangeRequest,
    db: Session = Depends(get_db),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> StandardResponse:
    user, tokens = exchange_qr_secret_for_tokens(
        db,
        payload.one_time_secret,
        user_agent=user_agent,
    )
    db.commit()
    
    result = TelegramQRExchangeResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type="bearer",
        user=UserPublic.from_orm(user),
    )
    
    return make_success_response(result=result)


__all__ = ["router"]
