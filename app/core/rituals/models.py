from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database.base import Base


JournalEntryType = ("morning", "evening")
WeeklyReviewStatus = ("in_progress", "completed", "auto_archived")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = Column(Date, nullable=False)
    type = Column(String, nullable=False)
    answers = Column(JSONB, nullable=False, default=dict)
    mood_score = Column(Integer, nullable=True)
    energy_score = Column(Integer, nullable=True)
    ai_feedback = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_journal_entries_user_date",
    JournalEntry.user_id,
    JournalEntry.date.desc(),
)


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    completed_steps = Column(JSONB, nullable=False, default=list)
    failed_steps = Column(JSONB, nullable=False, default=list)
    user_reflection = Column(Text, nullable=True)
    ai_analysis = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, default="in_progress")

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_weekly_reviews_user_week",
    WeeklyReview.user_id,
    WeeklyReview.week_start.desc(),
)


__all__ = [
    "JournalEntry",
    "WeeklyReview",
    "JournalEntryType",
    "WeeklyReviewStatus",
]
