from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.dependencies import get_current_user, get_db
from app.core.esoterics.schemas import DailyEnergyResponse
from app.core.esoterics.services import (
    calculate_moon,
    calculate_numerology,
    get_daily_tip,
)
from app.response import StandardResponse, make_success_response


router = APIRouter(prefix="/esoterics", tags=["esoterics"])


@router.get(
    "/today",
    response_model=StandardResponse,
    summary="Энергия дня",
)
def get_daily_energy_view(
    query_date: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StandardResponse:
    target_date = query_date or date.today()
    moon = calculate_moon(target_date)

    if user.date_of_birth is None:
        response = DailyEnergyResponse(
            date=target_date,
            moon=moon,
            numerology=None,
            daily_ai_tip="Сегодня хороший день, чтобы наблюдать, слушать себя и делать небольшие шаги.",
        )
        return make_success_response(result=response.model_dump(mode="json"))

    numerology = calculate_numerology(user.date_of_birth, target_date)
    tip = get_daily_tip(db, user, target_date, moon, numerology)
    response = DailyEnergyResponse(
        date=target_date,
        moon=moon,
        numerology=numerology,
        daily_ai_tip=tip,
    )
    return make_success_response(result=response.model_dump(mode="json"))


__all__ = ["router"]
