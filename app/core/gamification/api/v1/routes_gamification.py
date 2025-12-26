from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.core.gamification.schemas import (
    AchievementPublic,
    GamificationProfilePublic,
    LeaderboardEntry,
)
from app.core.gamification.services import (
    get_leaderboard,
    get_profile_payload,
    list_achievements_with_status,
)
from app.response import StandardResponse, make_success_response


router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get(
    "/profile",
    response_model=StandardResponse,
    summary="Get gamification profile",
)
def gamification_profile_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    payload = get_profile_payload(db, user.id)
    result = GamificationProfilePublic.model_validate(payload).model_dump(mode="json")
    return make_success_response(result=result)


@router.get(
    "/achievements",
    response_model=StandardResponse,
    summary="List achievements with obtained flag",
)
def gamification_achievements_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    achievements = list_achievements_with_status(db, user.id)
    result: List[dict] = [
        AchievementPublic.model_validate(item).model_dump(mode="json")
        for item in achievements
    ]
    return make_success_response(result=result)


@router.get(
    "/leaderboard",
    response_model=StandardResponse,
    summary="Leaderboard by XP",
)
def gamification_leaderboard_view(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    _ = user
    rows = get_leaderboard(db, limit=limit)
    result: List[dict] = [
        LeaderboardEntry.model_validate(item).model_dump(mode="json")
        for item in rows
    ]
    return make_success_response(result=result)


__all__ = ["router"]
