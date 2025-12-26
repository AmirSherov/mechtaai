from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import math
import httpx
from astral import moon
from redis import Redis
from sqlalchemy.orm import Session

from app.core.auth.models import User
from app.core.config import settings
from app.core.esoterics.schemas import MoonData, MoonPhaseEnum, NumerologyData
from app.response.response import APIError
from app.utils.redis_client import get_redis


MOON_DESCRIPTIONS: Dict[MoonPhaseEnum, str] = {
    MoonPhaseEnum.NEW_MOON: "Новолуние. Время закладывать намерения.",
    MoonPhaseEnum.WAXING_CRESCENT: "Молодая луна. Начинай действовать.",
    MoonPhaseEnum.FIRST_QUARTER: "Первая четверть. Преодолевай препятствия.",
    MoonPhaseEnum.WAXING_GIBBOUS: "Растущая луна. Набирай обороты.",
    MoonPhaseEnum.FULL_MOON: "Полнолуние. Пик энергии и ясности.",
    MoonPhaseEnum.WANING_GIBBOUS: "Убывающая луна. Делись опытом, учи.",
    MoonPhaseEnum.LAST_QUARTER: "Последняя четверть. Пересмотр планов.",
    MoonPhaseEnum.WANING_CRESCENT: "Старая луна. Очищение и отдых.",
}

MOON_EMOJIS: Dict[MoonPhaseEnum, str] = {
    MoonPhaseEnum.NEW_MOON: "🌑",
    MoonPhaseEnum.WAXING_CRESCENT: "🌒",
    MoonPhaseEnum.FIRST_QUARTER: "🌓",
    MoonPhaseEnum.WAXING_GIBBOUS: "🌔",
    MoonPhaseEnum.FULL_MOON: "🌕",
    MoonPhaseEnum.WANING_GIBBOUS: "🌖",
    MoonPhaseEnum.LAST_QUARTER: "🌗",
    MoonPhaseEnum.WANING_CRESCENT: "🌘",
}

NUMEROLOGY_KEYWORDS: Dict[int, List[str]] = {
    1: ["Старт", "Смелость", "Инициатива"],
    2: ["Партнерство", "Баланс", "Чуткость"],
    3: ["Творчество", "Коммуникация", "Радость"],
    4: ["Структура", "Дисциплина", "Стабильность"],
    5: ["Перемены", "Свобода", "Эксперимент"],
    6: ["Гармония", "Забота", "Дом"],
    7: ["Анализ", "Тишина", "Учеба"],
    8: ["Сила", "Результат", "Амбиции"],
    9: ["Завершение", "Мудрость", "Отпускание"],
}

NUMEROLOGY_MEANINGS: Dict[int, str] = {
    1: "новый старт и фокус на себе",
    2: "дипломатия и выстраивание связей",
    3: "самовыражение и легкость",
    4: "порядок и системность",
    5: "изменения и гибкость",
    6: "ответственность и забота",
    7: "анализ и внутренний фокус",
    8: "результат и сила воли",
    9: "завершение и отпускание",
}


def _reduce_to_digit(value: int) -> int:
    while value > 9:
        value = sum(int(d) for d in str(value))
    return value if value != 0 else 9


def calculate_moon(target_date: date) -> MoonData:
    moon_age = moon.phase(target_date)

    if moon_age < 1.0 or moon_age > 28.5:
        phase = MoonPhaseEnum.NEW_MOON
    elif moon_age < 6.4:
        phase = MoonPhaseEnum.WAXING_CRESCENT
    elif moon_age < 8.4:
        phase = MoonPhaseEnum.FIRST_QUARTER
    elif moon_age < 13.8:
        phase = MoonPhaseEnum.WAXING_GIBBOUS
    elif moon_age < 15.8:
        phase = MoonPhaseEnum.FULL_MOON
    elif moon_age < 21.1:
        phase = MoonPhaseEnum.WANING_GIBBOUS
    elif moon_age < 23.1:
        phase = MoonPhaseEnum.LAST_QUARTER
    else:
        phase = MoonPhaseEnum.WANING_CRESCENT

    synodic_month = 29.530588853
    illumination = (
        (1 - math.cos((moon_age * 2 * math.pi) / synodic_month)) / 2 * 100
    )

    return MoonData(
        phase=phase,
        illumination=round(illumination, 1),
        emoji=MOON_EMOJIS[phase],
        description=MOON_DESCRIPTIONS[phase],
    )


def calculate_numerology(
    birth_date: date,
    target_date: date,
) -> NumerologyData:
    personal_year = _reduce_to_digit(
        birth_date.day
        + birth_date.month
        + sum(int(d) for d in str(target_date.year))
    )
    personal_day = _reduce_to_digit(
        target_date.day + target_date.month + personal_year
    )
    return NumerologyData(
        personal_year=personal_year,
        personal_day=personal_day,
        keywords=NUMEROLOGY_KEYWORDS.get(personal_day, []),
    )


def _build_system_prompt() -> str:
    return (
        "Ты - эзотерический ментор. Твоя задача - дать короткий, емкий совет "
        "на день (максимум 2 предложения), основываясь на входных данных.\n\n"
        "Входные данные:\n"
        "- Фаза Луны: {moon_phase_desc}\n"
        "- Личный год пользователя: {personal_year} (Значение: {year_meaning})\n"
        "- Личный день пользователя: {personal_day} (Значение: {day_meaning})\n\n"
        "Тон: Вдохновляющий, но практичный. Без лишней мистики, ближе к психологии.\n"
        "Пример: \"Сегодня энергия убывающей луны совпадает с твоим днем анализа. "
        "Идеальное время, чтобы закрыть старые задачи и навести порядок на столе.\""
    )


def _call_ai_tip(
    moon_phase_desc: str,
    personal_year: int,
    personal_day: int,
) -> str:
    system_prompt = _build_system_prompt().format(
        moon_phase_desc=moon_phase_desc,
        personal_year=personal_year,
        year_meaning=NUMEROLOGY_MEANINGS.get(personal_year, ""),
        personal_day=personal_day,
        day_meaning=NUMEROLOGY_MEANINGS.get(personal_day, ""),
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Сформируй совет."},
    ]
    request_body = {
        "model": settings.ai_proxy_model,
        "messages": messages,
        "temperature": 0.4,
    }
    with httpx.Client(timeout=settings.ai_proxy_timeout_seconds) as client:
        response = client.post(settings.ai_proxy_url, json=request_body)
    response.raise_for_status()
    data = response.json()
    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("AI proxy returned empty content")
    return content.strip()


def _get_cache_ttl_seconds(
    target_date: date,
    user_tz: str,
) -> int:
    try:
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.now(tz)
    end_of_day = datetime.combine(target_date, datetime.max.time(), tzinfo=tz)
    if end_of_day <= now:
        return 60
    return int((end_of_day - now).total_seconds())


def _get_redis_client() -> Optional[Redis]:
    try:
        return get_redis()
    except Exception:
        return None


def _get_cached_tip_from_user(
    user: User,
    target_date: date,
) -> Optional[str]:
    cache = user.daily_tip_cache or {}
    if not isinstance(cache, dict):
        return None
    if cache.get("date") != target_date.isoformat():
        return None
    tip = cache.get("tip")
    return tip if isinstance(tip, str) else None


def _save_tip_to_user_cache(
    db: Session,
    user: User,
    target_date: date,
    tip: str,
) -> None:
    user.daily_tip_cache = {
        "date": target_date.isoformat(),
        "tip": tip,
    }
    db.add(user)
    db.commit()
    db.refresh(user)


def get_daily_tip(
    db: Session,
    user: User,
    target_date: date,
    moon: MoonData,
    numerology: NumerologyData,
) -> str:
    cache_key = f"tip_{user.id}_{target_date.isoformat()}"
    redis = _get_redis_client()
    if redis is not None:
        try:
            cached = redis.get(cache_key)
            if cached:
                return cached
        except Exception:
            redis = None

    if redis is None:
        cached = _get_cached_tip_from_user(user, target_date)
        if cached:
            return cached

    try:
        tip = _call_ai_tip(
            moon_phase_desc=moon.description,
            personal_year=numerology.personal_year,
            personal_day=numerology.personal_day,
        )
    except httpx.HTTPError as exc:
        raise APIError(
            code="ESOTERICS_AI_PROXY_ERROR",
            http_code=502,
            message=str(exc),
        )
    except Exception as exc:
        raise APIError(
            code="ESOTERICS_AI_FAILED",
            http_code=502,
            message=str(exc),
        )

    if redis is not None:
        try:
            ttl = _get_cache_ttl_seconds(target_date, user.time_zone)
            redis.setex(cache_key, ttl, tip)
        except Exception:
            pass
    else:
        _save_tip_to_user_cache(db, user, target_date, tip)

    return tip


__all__ = [
    "calculate_moon",
    "calculate_numerology",
    "get_daily_tip",
]
