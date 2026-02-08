from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.core.promocodes.schemas import (
    PromoCodeActivateRequest,
    PromoCodeActivateResponse,
)
from app.core.promocodes.services import activate_promo_code
from app.response import StandardResponse, make_success_response


router = APIRouter(prefix="/promocodes", tags=["promocodes"])


@router.post(
    "/activate",
    response_model=StandardResponse,
)
def activate_promocode(
    payload: PromoCodeActivateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    promo, expires_at = activate_promo_code(
        db,
        user=user,
        code=payload.code,
    )
    db.commit()
    return make_success_response(
        result=PromoCodeActivateResponse(
            code=promo.code,
            duration_code=promo.duration_code,  
            subscription_expires_at=expires_at,
        )
    )


__all__ = ["router"]
