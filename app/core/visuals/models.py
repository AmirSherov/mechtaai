from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database.base import Base


class VisualAsset(Base):
    __tablename__ = "visual_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    image_key = Column(String, nullable=False)
    local_path = Column(String, nullable=False)
    ai_prompt = Column(Text, nullable=False)
    provider = Column(String, nullable=False, default="dall-e-3")

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


Index(
    "ix_visual_assets_user_entity",
    VisualAsset.user_id,
    VisualAsset.entity_id,
)


__all__ = ["VisualAsset"]
