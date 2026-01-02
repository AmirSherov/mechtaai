from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.billing.models import SubscriptionPurchase
from app.response.response import APIError
from app.utils.redis_client import get_redis


SubscriptionDuration = Literal["month", "6m", "year"]


@dataclass(frozen=True)
class PlanOption:
    duration: SubscriptionDuration
    title: str
    description: str
    amount: int  # minor units
    currency: str
    days: int


PLAN_CATALOG: Dict[SubscriptionDuration, PlanOption] = {
    "month": PlanOption(
        duration="month",
        title="MechtaAI Pro",
        description="Подписка Pro на 1 месяц",
        amount=9900,
        currency="RUB",
        days=30,
    ),
    "6m": PlanOption(
        duration="6m",
        title="MechtaAI Pro",
        description="Подписка Pro на 6 месяцев",
        amount=49900,
        currency="RUB",
        days=180,
    ),
    "year": PlanOption(
        duration="year",
        title="MechtaAI Pro",
        description="Подписка Pro на 1 год",
        amount=89900,
        currency="RUB",
        days=365,
    ),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_pro_active(user: User) -> bool:
    if user.plan_tier != "pro":
        return False
    if user.subscription_expires_at is None:
        return False
    return user.subscription_expires_at > _utc_now()


def _invalidate_me_cache(user_id: UUID) -> None:
    try:
        redis = get_redis()
        redis.delete(f"me:user:{user_id}")
    except Exception:
        pass


def _get_user_by_telegram_id(db: Session, telegram_id: int) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user is None:
        raise APIError(
            code="BILLING_TELEGRAM_USER_NOT_FOUND",
            http_code=404,
            message="User not found. Run /start first.",
        )
    return user


def create_telegram_invoice(
    db: Session,
    *,
    telegram_id: int,
    duration: SubscriptionDuration,
) -> Tuple[SubscriptionPurchase, PlanOption]:
    user = _get_user_by_telegram_id(db, telegram_id)

    if _is_pro_active(user):
        raise APIError(
            code="BILLING_SUBSCRIPTION_ALREADY_ACTIVE",
            http_code=409,
            message="Subscription is already active",
            details={"subscription_expires_at": user.subscription_expires_at},
        )

    option = PLAN_CATALOG.get(duration)
    if option is None:
        raise APIError(
            code="BILLING_UNKNOWN_DURATION",
            http_code=400,
            message="Unknown subscription duration",
        )

    pending = (
        db.query(SubscriptionPurchase)
        .filter(
            SubscriptionPurchase.user_id == user.id,
            SubscriptionPurchase.status == "pending",
        )
        .order_by(SubscriptionPurchase.created_at.desc())
        .first()
    )
    if pending is not None:
        pending.status = "canceled"
        db.add(pending)

    # invoice payload must be <= 128 bytes (Telegram). Keep it short & opaque.
    # Example: pro:3fa85f64... + random suffix to avoid guessing.
    payload = f"pro:{uuid.uuid4().hex}:{secrets.token_hex(4)}"

    purchase = SubscriptionPurchase(
        user_id=user.id,
        plan_tier="pro",
        duration_code=duration,
        amount=option.amount,
        currency=option.currency,
        status="pending",
        invoice_payload=payload,
    )
    db.add(purchase)
    db.flush()
    db.refresh(purchase)

    return purchase, option


def validate_precheckout(
    db: Session,
    *,
    telegram_id: int,
    invoice_payload: str,
    currency: str,
    total_amount: int,
) -> SubscriptionPurchase:
    purchase = (
        db.query(SubscriptionPurchase)
        .filter(SubscriptionPurchase.invoice_payload == invoice_payload)
        .first()
    )
    if purchase is None:
        raise APIError(
            code="BILLING_INVOICE_NOT_FOUND",
            http_code=404,
            message="Invoice not found",
        )

    user = _get_user_by_telegram_id(db, telegram_id)
    if purchase.user_id != user.id:
        raise APIError(
            code="BILLING_INVOICE_FORBIDDEN",
            http_code=403,
            message="Invoice does not belong to this user",
        )

    if purchase.status != "pending":
        raise APIError(
            code="BILLING_INVOICE_NOT_PENDING",
            http_code=409,
            message="Invoice is not pending",
            details={"status": purchase.status},
        )

    if _is_pro_active(user):
        raise APIError(
            code="BILLING_SUBSCRIPTION_ALREADY_ACTIVE",
            http_code=409,
            message="Subscription is already active",
            details={"subscription_expires_at": user.subscription_expires_at},
        )

    option = PLAN_CATALOG.get(purchase.duration_code)  # type: ignore[arg-type]
    if option is None:
        raise APIError(
            code="BILLING_UNKNOWN_DURATION",
            http_code=400,
            message="Unknown subscription duration",
        )

    if currency != option.currency or total_amount != option.amount:
        raise APIError(
            code="BILLING_AMOUNT_MISMATCH",
            http_code=400,
            message="Payment amount mismatch",
            details={
                "expected_amount": option.amount,
                "expected_currency": option.currency,
                "got_amount": total_amount,
                "got_currency": currency,
            },
        )

    return purchase


def apply_successful_payment(
    db: Session,
    *,
    telegram_id: int,
    invoice_payload: str,
    currency: str,
    total_amount: int,
    telegram_payment_charge_id: str,
    provider_payment_charge_id: str,
    raw_successful_payment: Dict[str, Any] | None,
) -> Tuple[SubscriptionPurchase, datetime]:
    purchase = (
        db.query(SubscriptionPurchase)
        .filter(SubscriptionPurchase.invoice_payload == invoice_payload)
        .first()
    )
    if purchase is None:
        raise APIError(
            code="BILLING_INVOICE_NOT_FOUND",
            http_code=404,
            message="Invoice not found",
        )

    user = _get_user_by_telegram_id(db, telegram_id)
    if purchase.user_id != user.id:
        raise APIError(
            code="BILLING_INVOICE_FORBIDDEN",
            http_code=403,
            message="Invoice does not belong to this user",
        )

    option = PLAN_CATALOG.get(purchase.duration_code)  # type: ignore[arg-type]
    if option is None:
        raise APIError(
            code="BILLING_UNKNOWN_DURATION",
            http_code=400,
            message="Unknown subscription duration",
        )

    if currency != option.currency or total_amount != option.amount:
        raise APIError(
            code="BILLING_AMOUNT_MISMATCH",
            http_code=400,
            message="Payment amount mismatch",
            details={
                "expected_amount": option.amount,
                "expected_currency": option.currency,
                "got_amount": total_amount,
                "got_currency": currency,
            },
        )

    if purchase.status == "paid":
        if (
            purchase.telegram_payment_charge_id == telegram_payment_charge_id
            and purchase.provider_payment_charge_id == provider_payment_charge_id
            and purchase.expires_at is not None
        ):
            return purchase, purchase.expires_at
        raise APIError(
            code="BILLING_ALREADY_PAID",
            http_code=409,
            message="Purchase already marked as paid",
        )

    if purchase.status != "pending":
        raise APIError(
            code="BILLING_INVOICE_NOT_PENDING",
            http_code=409,
            message="Invoice is not pending",
            details={"status": purchase.status},
        )

    now = _utc_now()
    starts_at = now
    if user.subscription_expires_at and user.subscription_expires_at > now:
        starts_at = user.subscription_expires_at
    expires_at = starts_at + timedelta(days=option.days)

    purchase.status = "paid"
    purchase.paid_at = now
    purchase.starts_at = starts_at
    purchase.expires_at = expires_at
    purchase.telegram_payment_charge_id = telegram_payment_charge_id
    purchase.provider_payment_charge_id = provider_payment_charge_id
    if raw_successful_payment is not None:
        purchase.raw_successful_payment = raw_successful_payment

    user.plan_tier = "pro"
    user.subscription_expires_at = expires_at

    db.add(purchase)
    db.add(user)
    _invalidate_me_cache(user.id)

    return purchase, expires_at


__all__ = [
    "SubscriptionDuration",
    "PLAN_CATALOG",
    "create_telegram_invoice",
    "validate_precheckout",
    "apply_successful_payment",
]
