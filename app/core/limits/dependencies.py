from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.core.limits.services import ResourceType, check_and_spend


def check_text_quota(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    check_and_spend(db, user, ResourceType.AI_TEXT)


def check_image_quota(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    check_and_spend(db, user, ResourceType.AI_IMAGE)


__all__ = ["check_text_quota", "check_image_quota"]
