from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.core.areas.models import Area


DEFAULT_AREAS: List[dict] = [
    {"id": "money_business", "title": "Деньги и бизнес", "order_index": 1},
    {"id": "health_body", "title": "Здоровье и тело", "order_index": 2},
    {"id": "mind_energy", "title": "Ум и энергия", "order_index": 3},
    {
        "id": "relationships",
        "title": "Отношения и близкие / окружение",
        "order_index": 4,
    },
    {"id": "home_life", "title": "Дом и быт", "order_index": 5},
    {"id": "growth_knowledge", "title": "Рост и развитие", "order_index": 6},
    {
        "id": "freedom_experience",
        "title": "Свобода и впечатления",
        "order_index": 7,
    },
    {"id": "contribution_meaning", "title": "Вклад и смысл", "order_index": 8},
]


def ensure_default_areas(db: Session) -> None:
    """
    Инициализирует таблицу areas 8 базовыми сферами,
    если таблица пуста.
    """
    has_rows = db.query(Area.id).first()
    if has_rows is not None:
        return

    for item in DEFAULT_AREAS:
        area = Area(
            id=item["id"],
            title=item["title"],
            order_index=item["order_index"],
            is_active=True,
        )
        db.add(area)

    db.commit()


__all__ = ["DEFAULT_AREAS", "ensure_default_areas"]

