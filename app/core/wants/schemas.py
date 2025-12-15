from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


WantsRawStatus = Literal["draft", "completed"]
WantsRawChunkExercise = Literal["stream", "future_me"]


class WantsRawPublic(BaseModel):
    id: UUID = Field(..., description="ID записи wants_raw.")
    status: WantsRawStatus = Field(
        ..., description="Статус: draft (в работе) или completed (завершён)."
    )

    stream_started_at: datetime | None = Field(
        default=None,
        description=(
            "Когда пользователь начал упражнение 'Поток Я хочу'. "
            "Используется для аналитики/таймлайна; сервер не блокирует добавление текста по таймеру."
        ),
    )
    stream_timer_seconds: int = Field(
        default=600,
        description=(
            "Рекомендуемая длительность упражнения 'Поток Я хочу' в секундах (по умолчанию 600). "
            "Это значение для UI/клиента (таймер/подсказка), а не серверное ограничение."
        ),
    )
    raw_wants_stream: str | None = Field(
        default=None,
        description="Собранный текст потока (строки склеены через \\n).",
    )
    stream_completed_at: datetime | None = Field(
        default=None,
        description="Когда поток был завершён (через 'стоп' или /stream/finish).",
    )

    raw_future_me: str | None = Field(
        default=None,
        description="Ответ на упражнение 'Мне 40' (может писаться целиком или дозаполняться чанками).",
    )
    future_me_completed_at: datetime | None = Field(
        default=None,
        description="Когда упражнение 'Мне 40' было помечено завершённым.",
    )

    raw_envy: str | None = Field(
        default=None,
        description="Reverse-вопрос: кому/чему завидуешь и почему.",
    )
    raw_regrets: str | None = Field(
        default=None,
        description="Reverse-вопрос: о чём жалеешь / что бы сделал иначе.",
    )
    raw_what_to_do_5y: str | None = Field(
        default=None,
        description="Reverse-вопрос: что стоит делать ближайшие 5 лет.",
    )
    reverse_completed_at: datetime | None = Field(
        default=None,
        description="Когда 3 reverse-ответа были заполнены и раздел помечен завершённым.",
    )

    completed_at: datetime | None = Field(
        default=None,
        description="Когда весь wants был завершён (status=completed).",
    )
    created_at: datetime = Field(..., description="Когда запись создана.")
    updated_at: datetime = Field(..., description="Когда запись обновлялась последний раз.")

    model_config = ConfigDict(from_attributes=True)


class WantsDraftRef(BaseModel):
    raw_id: UUID = Field(..., description="ID текущего wants_raw (draft).")
    status: WantsRawStatus = Field(..., description="Текущий статус wants_raw.")


class WantsStreamStartPublic(BaseModel):
    raw_id: UUID = Field(..., description="ID текущего wants_raw (draft).")
    stream_started_at: datetime | None = Field(
        default=None, description="Время старта упражнения 'Поток Я хочу'."
    )
    stream_timer_seconds: int = Field(
        ..., description="Рекомендуемая длительность таймера (для UI), сек."
    )
    stream_completed_at: datetime | None = Field(
        default=None, description="Время завершения упражнения, если уже завершено."
    )


class WantsTextIn(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=50_000,
        description=(
            "Одна порция текста (обычно 1 строка/мысль). "
            "Для потока можно отправлять много раз."
        ),
    )


class WantsStreamAppendPublic(BaseModel):
    raw_id: UUID = Field(..., description="ID текущего wants_raw (draft).")
    is_completed: bool = Field(
        ..., description="True если упражнение завершили словом 'стоп'/'stop'."
    )
    raw_wants_stream_preview: str | None = Field(
        default=None,
        description="Превью последней части собранного текста потока (для UI).",
    )


class WantsFutureMeSetIn(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=200_000,
        description=(
            "Текст упражнения 'Мне 40' целиком. "
            "Если нужно дописывать частями — используйте /future-me/append."
        ),
    )


class WantsFutureMePublic(BaseModel):
    raw_id: UUID = Field(..., description="ID текущего wants_raw (draft).")
    raw_future_me: str | None = Field(
        default=None, description="Текущий текст упражнения 'Мне 40'."
    )
    future_me_completed_at: datetime | None = Field(
        default=None, description="Время завершения упражнения 'Мне 40'."
    )


class WantsReverseUpdateIn(BaseModel):
    raw_envy: str | None = Field(
        default=None,
        description="Ответ на вопрос про зависть (можно обновлять частично).",
    )
    raw_regrets: str | None = Field(
        default=None,
        description="Ответ на вопрос про сожаления (можно обновлять частично).",
    )
    raw_what_to_do_5y: str | None = Field(
        default=None,
        description="Ответ на вопрос 'что делать 5 лет' (можно обновлять частично).",
    )


class WantsReversePublic(BaseModel):
    raw_id: UUID = Field(..., description="ID текущего wants_raw (draft).")
    raw_envy: str | None = Field(default=None, description="Сохранённый raw_envy.")
    raw_regrets: str | None = Field(default=None, description="Сохранённый raw_regrets.")
    raw_what_to_do_5y: str | None = Field(
        default=None, description="Сохранённый raw_what_to_do_5y."
    )
    reverse_completed_at: datetime | None = Field(
        default=None,
        description="Ставится автоматически, когда заполнены все 3 ответа.",
    )


class WantsProgressPublic(BaseModel):
    raw_id: UUID = Field(..., description="ID текущего wants_raw (draft).")
    status: WantsRawStatus = Field(..., description="Текущий статус wants_raw.")
    stream_done: bool = Field(
        ..., description="Упражнение 'Поток Я хочу' завершено (есть stream_completed_at)."
    )
    future_me_done: bool = Field(
        ...,
        description="Упражнение 'Мне 40' завершено (есть future_me_completed_at).",
    )
    reverse_done: bool = Field(
        ...,
        description="Reverse-вопросы завершены (есть reverse_completed_at).",
    )
    all_done: bool = Field(
        ...,
        description="Все 3 упражнения завершены (stream_done && future_me_done && reverse_done).",
    )


__all__ = [
    "WantsRawPublic",
    "WantsDraftRef",
    "WantsStreamStartPublic",
    "WantsTextIn",
    "WantsStreamAppendPublic",
    "WantsFutureMeSetIn",
    "WantsFutureMePublic",
    "WantsReverseUpdateIn",
    "WantsReversePublic",
    "WantsProgressPublic",
]
