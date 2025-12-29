import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Index, Boolean, Float, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CardProgress(Base):
    __tablename__ = "card_progress"

    __table_args__ = (
        # 1 прогресс на (user, card_level)
        UniqueConstraint("user_id", "card_level_id", name="uq_user_card_level_progress"),
        # 1 ACTIVE уровень на (user, card) через partial unique index (Postgres)
        Index(
            "uq_user_card_active_level",
            "user_id",
            "card_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Нужен, чтобы:
    # - быстро выбирать прогресс по карточке
    # - гарантировать "один активный уровень на карточку"
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ключевое: прогресс теперь на уровень
    card_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("card_levels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Состояние памяти (пока простое, но совместимо с FSRS-подходом)
    stability: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)   # в днях
    difficulty: Mapped[float] = mapped_column(Float, default=5.0, nullable=False) # 1..10 условно

    next_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="card_progress")
    card: Mapped["Card"] = relationship("Card", back_populates="progress")
    card_level: Mapped["CardLevel"] = relationship("CardLevel", back_populates="progress")
