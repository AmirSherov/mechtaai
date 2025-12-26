from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class MoonPhaseEnum(str, Enum):
    NEW_MOON = "new_moon"
    WAXING_CRESCENT = "waxing_crescent"
    FIRST_QUARTER = "first_quarter"
    WAXING_GIBBOUS = "waxing_gibbous"
    FULL_MOON = "full_moon"
    WANING_GIBBOUS = "waning_gibbous"
    LAST_QUARTER = "last_quarter"
    WANING_CRESCENT = "waning_crescent"


class MoonData(BaseModel):
    phase: MoonPhaseEnum
    illumination: float
    emoji: str
    description: str


class NumerologyData(BaseModel):
    personal_year: int
    personal_day: int
    keywords: List[str]


class DailyEnergyResponse(BaseModel):
    date: date
    moon: MoonData
    numerology: Optional[NumerologyData] = None
    daily_ai_tip: str


__all__ = [
    "MoonPhaseEnum",
    "MoonData",
    "NumerologyData",
    "DailyEnergyResponse",
]
