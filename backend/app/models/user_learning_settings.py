import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserLearningSettings(Base):
    __tablename__ = "user_learning_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    desired_retention: Mapped[float] = mapped_column(Float, default=0.90, nullable=False)

    initial_stability: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    initial_difficulty: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)

    promote_stability_multiplier: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    promote_difficulty_delta: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="learning_settings", uselist=False)
