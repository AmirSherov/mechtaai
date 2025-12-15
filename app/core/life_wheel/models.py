from __future__ import annotations

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database.base import Base


class LifeWheel(Base):
    __tablename__ = "life_wheels"

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
    scores = Column(JSON, nullable=False)
    note = Column(Text, nullable=True)

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
    "ix_life_wheels_user_id_created_at",
    LifeWheel.user_id,
    LifeWheel.created_at.desc(),
)


__all__ = ["LifeWheel"]

