import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Float, DateTime
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserLearningSettings(Base):
    __tablename__ = "user_learning_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Базовый интервал в минутах (например: 1440 = 1 день)
    base_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)

    # Насколько уровень карточки влияет на интервал
    level_factor: Mapped[float] = mapped_column(Float, default=1, nullable=False)

    # Насколько streak влияет на интервал
    streak_factor: Mapped[float] = mapped_column(Float, default=0.55, nullable=False)

    # Штраф при ответе "again"
    again_penalty: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationship с пользователем
    user: Mapped["User"] = relationship("User", back_populates="learning_settings", uselist=False)
