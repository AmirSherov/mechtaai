from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.billing.services import PLAN_CATALOG
from app.core.promocodes.models import PromoCode, PromoRedemption
from app.response.response import APIError
from app.utils.redis_client import get_redis


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _invalidate_me_cache(user_id) -> None:
    try:
        redis = get_redis()
        redis.delete(f"me:user:{user_id}")
    except Exception:
        pass


def _normalize_expires_at(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _generate_promo_code() -> str:
    letters = random.sample(string.ascii_uppercase, 2)
    digits = [random.choice(string.digits) for _ in range(6)]
    chars = letters + digits
    random.shuffle(chars)
    return "".join(chars)


def generate_unique_promo_code(db: Session, *, max_attempts: int = 20) -> str:
    for _ in range(max_attempts):
        code = _generate_promo_code()
        exists = (
            db.query(PromoCode)
            .filter(PromoCode.code == code)
            .first()
        )
        if not exists:
            return code
    raise APIError(
        code="PROMO_CODE_GENERATION_FAILED",
        http_code=500,
        message="Failed to generate unique promo code",
    )


def create_promo_code(
    db: Session,
    *,
    name: str,
    duration_code: str,
    expires_at: datetime,
    created_by: Optional[User],
) -> PromoCode:
    if duration_code not in PLAN_CATALOG:
        raise APIError(
            code="PROMO_INVALID_DURATION",
            http_code=400,
            message="Invalid promo duration",
        )

    expires_at = _normalize_expires_at(expires_at)

    now = _utc_now()
    if expires_at <= now:
        raise APIError(
            code="PROMO_EXPIRES_AT_PAST",
            http_code=400,
            message="Promo expiration must be in the future",
        )

    code = generate_unique_promo_code(db)
    promo = PromoCode(
        code=code,
        name=name,
        duration_code=duration_code,
        expires_at=expires_at,
        created_by=created_by.id if created_by else None,
        is_active=True,
    )
    db.add(promo)
    db.flush()
    db.refresh(promo)
    return promo


def update_promo_code(
    db: Session,
    *,
    promo: PromoCode,
    name: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    is_active: Optional[bool] = None,
) -> PromoCode:
    if name is not None:
        promo.name = name

    if expires_at is not None:
        promo.expires_at = _normalize_expires_at(expires_at)

    if is_active is not None:
        promo.is_active = is_active

    db.add(promo)
    return promo


def activate_promo_code(
    db: Session,
    *,
    user: User,
    code: str,
) -> Tuple[PromoCode, datetime]:
    code = code.strip().upper()
    promo = (
        db.query(PromoCode)
        .filter(PromoCode.code == code)
        .first()
    )
    if promo is None or not promo.is_active:
        raise APIError(
            code="PROMO_NOT_FOUND",
            http_code=404,
            message="Promo code not found",
        )

    now = _utc_now()
    if promo.expires_at is not None and promo.expires_at <= now:
        raise APIError(
            code="PROMO_EXPIRED",
            http_code=400,
            message="Promo code has expired",
        )

    already_used = (
        db.query(PromoRedemption)
        .filter(
            PromoRedemption.promo_code_id == promo.id,
            PromoRedemption.user_id == user.id,
        )
        .first()
    )
    if already_used is not None:
        raise APIError(
            code="PROMO_ALREADY_USED",
            http_code=409,
            message="Promo code already used",
        )

    option = PLAN_CATALOG.get(promo.duration_code)
    if option is None:
        raise APIError(
            code="PROMO_INVALID_DURATION",
            http_code=400,
            message="Invalid promo duration",
        )

    starts_at = now
    if user.subscription_expires_at and user.subscription_expires_at > now:
        starts_at = user.subscription_expires_at
    expires_at = starts_at + timedelta(days=option.days)

    user.plan_tier = "pro"
    user.subscription_expires_at = expires_at
    db.add(user)

    redemption = PromoRedemption(
        promo_code_id=promo.id,
        user_id=user.id,
        redeemed_at=now,
    )
    db.add(redemption)
    _invalidate_me_cache(user.id)

    return promo, expires_at


__all__ = [
    "create_promo_code",
    "update_promo_code",
    "activate_promo_code",
]
