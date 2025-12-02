from __future__ import annotations

from pydantic import BaseModel
from pydantic.config import ConfigDict


class AreaPublic(BaseModel):
    id: str
    title: str
    description: str | None
    order_index: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AreaCreate(BaseModel):
    id: str
    title: str
    description: str | None = None
    order_index: int = 1
    is_active: bool = True


class AreaUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    order_index: int | None = None
    is_active: bool | None = None


__all__ = ["AreaPublic", "AreaCreate", "AreaUpdate"]

