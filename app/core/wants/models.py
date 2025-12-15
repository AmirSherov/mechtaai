from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.base import Base


WantsRawStatus = Enum(
    "draft",
    "completed",
    name="wants_raw_status",
)

WantsRawChunkExercise = Enum(
    "stream",
    "future_me",
    name="wants_raw_chunk_exercise",
)


class WantsRaw(Base):
    __tablename__ = "wants_raw"

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
    status = Column(WantsRawStatus, nullable=False, default="draft")

    stream_started_at = Column(DateTime(timezone=True), nullable=True)
    stream_timer_seconds = Column(Integer, nullable=False, default=600)
    raw_wants_stream = Column(Text, nullable=True)
    stream_completed_at = Column(DateTime(timezone=True), nullable=True)

    raw_future_me = Column(Text, nullable=True)
    future_me_completed_at = Column(DateTime(timezone=True), nullable=True)

    raw_envy = Column(Text, nullable=True)
    raw_regrets = Column(Text, nullable=True)
    raw_what_to_do_5y = Column(Text, nullable=True)
    reverse_completed_at = Column(DateTime(timezone=True), nullable=True)

    completed_at = Column(DateTime(timezone=True), nullable=True)

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

    chunks = relationship(
        "WantsRawChunk",
        back_populates="wants_raw",
        cascade="all, delete-orphan",
    )


Index(
    "idx_wants_raw_user_updated",
    WantsRaw.user_id,
    WantsRaw.updated_at.desc(),
)

Index(
    "uq_wants_raw_user_draft",
    WantsRaw.user_id,
    unique=True,
    postgresql_where=(WantsRaw.status == "draft"),
)


class WantsRawChunk(Base):
    __tablename__ = "wants_raw_chunks"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    wants_raw_id = Column(
        UUID(as_uuid=True),
        ForeignKey("wants_raw.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise = Column(WantsRawChunkExercise, nullable=False)
    text = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    wants_raw = relationship("WantsRaw", back_populates="chunks")


Index(
    "ix_wants_raw_chunks_wants_raw_id_created_at",
    WantsRawChunk.wants_raw_id,
    WantsRawChunk.created_at.desc(),
)


__all__ = [
    "WantsRaw",
    "WantsRawChunk",
    "WantsRawStatus",
    "WantsRawChunkExercise",
]

