from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Dict
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.limits.models import UserUsage
from app.response.response import APIError
from app.utils.redis_client import get_redis


class ResourceType(str, Enum):
    AI_TEXT = "AI_TEXT"
    AI_IMAGE = "AI_IMAGE"


LIMITS_FREE = {
    ResourceType.AI_TEXT: 5,
    ResourceType.AI_IMAGE: 1,
}

LIMITS_PRO = {
    ResourceType.AI_TEXT: 100,
    ResourceType.AI_IMAGE: 20,
}


@dataclass
class UsageSnapshot:
    plan: str
    text_used: int
    text_limit: int
    image_used: int
    image_limit: int


def _current_period_start(target_date: date | None = None) -> date:
    target = target_date or date.today()
    return date(target.year, target.month, 1)


def _is_pro(user: User) -> bool:
    if user.plan_tier != "pro":
        return False
    if user.subscription_expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    return user.subscription_expires_at > now


def _get_limits(user: User) -> Dict[ResourceType, int]:
    return LIMITS_PRO if _is_pro(user) else LIMITS_FREE


def _ensure_usage(db: Session, user_id: UUID) -> UserUsage:
    usage = (
        db.query(UserUsage)
        .filter(UserUsage.user_id == user_id)
        .first()
    )
    if usage is not None:
        return usage

    usage = UserUsage(
        user_id=user_id,
        period_start=_current_period_start(),
        text_usage=0,
        image_usage=0,
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def _maybe_reset_period(usage: UserUsage, today: date) -> bool:
    current_period = _current_period_start(today)
    if usage.period_start != current_period:
        usage.period_start = current_period
        usage.text_usage = 0
        usage.image_usage = 0
        return True
    return False


def check_and_spend(
    db: Session,
    user: User,
    resource_type: ResourceType,
) -> UserUsage:
    usage = _ensure_usage(db, user.id)
    _maybe_reset_period(usage, date.today())
    limits = _get_limits(user)
    limit = limits[resource_type]

    if resource_type == ResourceType.AI_TEXT:
        current = usage.text_usage
    else:
        current = usage.image_usage

    if current >= limit:
        raise APIError(
            code="QUOTA_EXCEEDED",
            http_code=403,
            message=(
                f"Лимит генераций исчерпан ({current}/{limit}). "
                "Перейдите на Pro."
            ),
            details={
                "resource": resource_type.value,
                "used": current,
                "limit": limit,
            },
        )

    if resource_type == ResourceType.AI_TEXT:
        usage.text_usage = current + 1
    else:
        usage.image_usage = current + 1

    db.add(usage)
    db.commit()
    db.refresh(usage)

    _invalidate_me_cache(user.id)

    return usage


def get_usage_snapshot(db: Session, user: User) -> UsageSnapshot:
    usage = _ensure_usage(db, user.id)
    _maybe_reset_period(usage, date.today())
    db.add(usage)
    db.commit()
    db.refresh(usage)

    limits = _get_limits(user)
    return UsageSnapshot(
        plan="pro" if _is_pro(user) else "free",
        text_used=usage.text_usage,
        text_limit=limits[ResourceType.AI_TEXT],
        image_used=usage.image_usage,
        image_limit=limits[ResourceType.AI_IMAGE],
    )


def _invalidate_me_cache(user_id: UUID) -> None:
    try:
        redis = get_redis()
        redis.delete(f"me:user:{user_id}")
    except Exception:
        pass


__all__ = [
    "ResourceType",
    "UsageSnapshot",
    "check_and_spend",
    "get_usage_snapshot",
]
