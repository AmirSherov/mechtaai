from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database.base import Base


class FutureStoryDraft(Base):
    __tablename__ = "future_story_drafts"

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
    answers = Column(JSONB, nullable=False, default=list)
    status = Column(String, nullable=False, default="in_progress")

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
    "ix_future_story_drafts_user_updated",
    FutureStoryDraft.user_id,
    FutureStoryDraft.updated_at.desc(),
)


class FutureStory(Base):
    __tablename__ = "future_stories"

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
    horizon_3y = Column(JSONB, nullable=False)
    horizon_5y = Column(JSONB, nullable=False)
    key_images = Column(JSONB, nullable=False, default=list)
    validation_notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_future_stories_user_created_at",
    FutureStory.user_id,
    FutureStory.created_at.desc(),
)


__all__ = [
    "FutureStoryDraft",
    "FutureStory",
]
