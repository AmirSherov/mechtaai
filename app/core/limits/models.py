from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID

from app.database.base import Base


class UserUsage(Base):
    __tablename__ = "user_usage"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    period_start = Column(Date, nullable=False)
    text_usage = Column(Integer, nullable=False, default=0)
    image_usage = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["UserUsage"]
