from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database.base import Base


GoalStatus = ("draft", "planned", "in_progress", "done", "dropped")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    area_id = Column(String, nullable=False)
    horizon = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    metric = Column(String, nullable=True)
    target_date = Column(Date, nullable=True)
    priority = Column(Integer, nullable=False, default=1)
    reason = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="planned")

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


Index(
    "ix_goals_user_created_at",
    Goal.user_id,
    Goal.created_at.desc(),
)


class GoalGeneration(Base):
    __tablename__ = "goal_generations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comment_for_user = Column(Text, nullable=True)
    suggested_to_drop = Column(JSONB, nullable=False, default=list)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_goal_generations_user_created_at",
    GoalGeneration.user_id,
    GoalGeneration.created_at.desc(),
)


__all__ = [
    "Goal",
    "GoalGeneration",
    "GoalStatus",
]
