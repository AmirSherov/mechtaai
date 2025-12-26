from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database.base import Base


class GamificationProfile(Base):
    __tablename__ = "gamification_profiles"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_xp = Column(Integer, nullable=False, default=0)
    current_level = Column(Integer, nullable=False, default=1)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_activity_date = Column(Date, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    xp_reward = Column(Integer, nullable=False, default=0)
    icon_url = Column(String, nullable=True)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    achievement_id = Column(
        String,
        ForeignKey("achievements.id", ondelete="CASCADE"),
        nullable=False,
    )
    obtained_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )


__all__ = [
    "GamificationProfile",
    "Achievement",
    "UserAchievement",
]
