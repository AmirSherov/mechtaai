from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.core.visuals.schemas import (
    VisualAssetPublic,
    VisualGenerateIn,
    VisualRegenerateIn,
)
from app.core.visuals.services import generate_and_save, list_story_assets, regenerate_asset
from app.core.gamification.services import (
    ActionType,
    award_action,
    build_gamification_event,
)
from app.core.limits.dependencies import check_image_quota
from app.response import StandardResponse, make_success_response


router = APIRouter(prefix="/visuals", tags=["visuals"])


@router.post(
    "/generate-story-image",
    response_model=StandardResponse,
    dependencies=[Depends(check_image_quota)],
    summary="Сгенерировать изображение истории",
)
def generate_story_image_view(
    payload: VisualGenerateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    asset = generate_and_save(
        db=db,
        user_id=user.id,
        story_id=payload.story_id,
        image_key=payload.image_key,
    )
    award_result = award_action(db, user.id, ActionType.VISION_BOARD_CREATED)
    result = VisualAssetPublic.model_validate(asset).model_dump(mode="json")
    result["gamification_event"] = build_gamification_event(
        ActionType.VISION_BOARD_CREATED,
        award_result,
    )
    return make_success_response(result=result)


@router.get(
    "/story-gallery/{story_id}",
    response_model=StandardResponse,
    summary="Галерея изображений истории",
)
def story_gallery_view(
    story_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    assets = list_story_assets(db=db, user_id=user.id, story_id=story_id)
    result = [VisualAssetPublic.model_validate(a).model_dump(mode="json") for a in assets]
    return make_success_response(result=result)


@router.post(
    "/regenerate",
    response_model=StandardResponse,
    dependencies=[Depends(check_image_quota)],
    summary="Перегенерация изображения",
)
def regenerate_view(
    payload: VisualRegenerateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    asset = regenerate_asset(db=db, user_id=user.id, asset_id=payload.asset_id)
    result = VisualAssetPublic.model_validate(asset).model_dump(mode="json")
    return make_success_response(result=result)


__all__ = ["router"]
