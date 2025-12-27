from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class GamificationProfilePublic(BaseModel):
    level: int
    level_title: str
    xp: int
    xp_to_next_level: int
    streak: int
    longest_streak: int


class AchievementPublic(BaseModel):
    id: str
    title: str
    description: str
    xp_reward: int
    icon_url: str | None = None
    is_obtained: bool


class LeaderboardEntry(BaseModel):
    user_id: UUID
    first_name: str | None = None
    total_xp: int
    level: int


__all__ = [
    "GamificationProfilePublic",
    "AchievementPublic",
    "LeaderboardEntry",
]
