from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.billing.models import SubscriptionPurchase
from app.core.dependencies import get_current_admin, get_db
from app.core.promocodes.models import PromoCode, PromoRedemption
from app.core.promocodes.schemas import (
    PromoCodeCreate,
    PromoCodePublic,
    PromoCodeUpdate,
)
from app.core.promocodes.services import create_promo_code, update_promo_code
from app.response import Pagination, StandardResponse, make_success_response
from app.response.response import APIError


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/stats",
    response_model=StandardResponse,
)
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> StandardResponse:
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_paid_subscriptions = (
        db.query(func.count(SubscriptionPurchase.id))
        .filter(SubscriptionPurchase.status == "paid")
        .scalar()
        or 0
    )

    now = datetime.now(timezone.utc)
    total_active_subscriptions = (
        db.query(func.count(User.id))
        .filter(
            User.plan_tier == "pro",
            User.subscription_expires_at.isnot(None),
            User.subscription_expires_at > now,
        )
        .scalar()
        or 0
    )

    total_revenue_minor = (
        db.query(func.coalesce(func.sum(SubscriptionPurchase.amount), 0))
        .filter(SubscriptionPurchase.status == "paid")
        .scalar()
        or 0
    )
    total_revenue_rub = round(total_revenue_minor / 100, 2)

    return make_success_response(
        result={
            "total_users": total_users,
            "total_paid_subscriptions": total_paid_subscriptions,
            "total_active_subscriptions": total_active_subscriptions,
            "total_revenue_minor": total_revenue_minor,
            "total_revenue_rub": total_revenue_rub,
        }
    )


@router.get(
    "/users",
    response_model=StandardResponse,
)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> StandardResponse:
    total = db.query(func.count(User.id)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for user in users:
        items.append(
            {
                "id": str(user.id),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "telegram_id": user.telegram_id,
                "gender": user.gender,
                "plan_tier": user.plan_tier,
                "locale": user.locale,
                "date_of_birth": user.date_of_birth,
                "email": user.email,
            }
        )

    pagination = Pagination(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    return make_success_response(
        result={"items": items},
        pagination=pagination,
    )


@router.get(
    "/promocodes",
    response_model=StandardResponse,
)
def list_promocodes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> StandardResponse:
    total = db.query(func.count(PromoCode.id)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

    redemptions_subq = (
        db.query(
            PromoRedemption.promo_code_id.label("promo_code_id"),
            func.count(PromoRedemption.id).label("redemptions_count"),
        )
        .group_by(PromoRedemption.promo_code_id)
        .subquery()
    )

    rows = (
        db.query(PromoCode, func.coalesce(redemptions_subq.c.redemptions_count, 0))
        .outerjoin(
            redemptions_subq,
            PromoCode.id == redemptions_subq.c.promo_code_id,
        )
        .order_by(PromoCode.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for promo, count in rows:
        promo_out = PromoCodePublic.from_orm(promo)
        promo_out.redemptions_count = int(count or 0)
        items.append(promo_out)

    pagination = Pagination(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
    return make_success_response(
        result={"items": items},
        pagination=pagination,
    )


@router.post(
    "/promocodes",
    response_model=StandardResponse,
)
def create_promocode(
    payload: PromoCodeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> StandardResponse:
    promo = create_promo_code(
        db,
        name=payload.name,
        duration_code=payload.duration_code,
        expires_at=payload.expires_at,
        created_by=admin,
    )
    db.commit()
    db.refresh(promo)
    promo_out = PromoCodePublic.from_orm(promo)
    promo_out.redemptions_count = 0
    return make_success_response(result=promo_out)


@router.put(
    "/promocodes/{promo_id}",
    response_model=StandardResponse,
)
def update_promocode(
    promo_id: uuid.UUID,
    payload: PromoCodeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> StandardResponse:
    promo = (
        db.query(PromoCode)
        .filter(PromoCode.id == promo_id)
        .first()
    )
    if promo is None:
        raise APIError(
            code="PROMO_NOT_FOUND",
            http_code=404,
            message="Promo code not found",
        )

    promo = update_promo_code(
        db,
        promo=promo,
        name=payload.name,
        expires_at=payload.expires_at,
        is_active=payload.is_active,
    )
    db.commit()
    db.refresh(promo)
    redemption_count = (
        db.query(func.count(PromoRedemption.id))
        .filter(PromoRedemption.promo_code_id == promo.id)
        .scalar()
        or 0
    )
    promo_out = PromoCodePublic.from_orm(promo)
    promo_out.redemptions_count = redemption_count
    return make_success_response(result=promo_out)


__all__ = ["router"]
