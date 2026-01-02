from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.billing.schemas import (
    TelegramCreateInvoiceRequest,
    TelegramCreateInvoiceResponse,
    TelegramInvoicePrice,
    TelegramPreCheckoutValidateRequest,
    TelegramPreCheckoutValidateResponse,
    TelegramSuccessfulPaymentRequest,
    TelegramSuccessfulPaymentResponse,
)
from app.core.billing.services import (
    apply_successful_payment,
    create_telegram_invoice,
    validate_precheckout,
)
from app.core.config import settings
from app.core.dependencies import get_db
from app.response import StandardResponse, make_success_response
from app.response.response import APIError


router = APIRouter(prefix="/billing", tags=["billing"])


def _require_bot_secret(
    bot_secret: str | None = Header(default=None, alias="X-Bot-Secret"),
) -> None:
    if not bot_secret or bot_secret != settings.bot_secret_key:
        raise APIError(
            code="BILLING_FORBIDDEN",
            http_code=403,
            message="Access denied for non-bot request",
        )


@router.post(
    "/telegram/invoice",
    response_model=StandardResponse,
    summary="Create Telegram invoice (bot-only)",
)
def telegram_create_invoice(
    payload: TelegramCreateInvoiceRequest,
    _: None = Depends(_require_bot_secret),
    db: Session = Depends(get_db),
) -> StandardResponse:
    purchase, option = create_telegram_invoice(
        db,
        telegram_id=payload.telegram_id,
        duration=payload.duration,
    )
    db.commit()
    result = TelegramCreateInvoiceResponse(
        purchase_id=purchase.id,
        invoice_payload=purchase.invoice_payload,
        title=option.title,
        description=option.description,
        currency=option.currency,
        prices=[TelegramInvoicePrice(label=f"Pro ({payload.duration})", amount=option.amount)],
        duration=payload.duration,
        amount=option.amount,
    )
    return make_success_response(result=result)


@router.post(
    "/telegram/precheckout/validate",
    response_model=StandardResponse,
    summary="Validate Telegram pre-checkout query (bot-only)",
)
def telegram_validate_precheckout(
    payload: TelegramPreCheckoutValidateRequest,
    _: None = Depends(_require_bot_secret),
    db: Session = Depends(get_db),
) -> StandardResponse:
    validate_precheckout(
        db,
        telegram_id=payload.telegram_id,
        invoice_payload=payload.invoice_payload,
        currency=payload.currency,
        total_amount=payload.total_amount,
    )
    return make_success_response(
        result=TelegramPreCheckoutValidateResponse(allowed=True)
    )


@router.post(
    "/telegram/payment/success",
    response_model=StandardResponse,
    summary="Apply successful Telegram payment (bot-only)",
)
def telegram_successful_payment(
    payload: TelegramSuccessfulPaymentRequest,
    _: None = Depends(_require_bot_secret),
    db: Session = Depends(get_db),
) -> StandardResponse:
    purchase, expires_at = apply_successful_payment(
        db,
        telegram_id=payload.telegram_id,
        invoice_payload=payload.invoice_payload,
        currency=payload.currency,
        total_amount=payload.total_amount,
        telegram_payment_charge_id=payload.telegram_payment_charge_id,
        provider_payment_charge_id=payload.provider_payment_charge_id,
        raw_successful_payment=payload.raw_successful_payment,
    )
    db.commit()
    return make_success_response(
        result=TelegramSuccessfulPaymentResponse(
            purchase_id=purchase.id,
            status=purchase.status,
            subscription_expires_at=expires_at,
        )
    )


__all__ = ["router"]

