import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Enum, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.enums import ReviewRating


class CardReviewHistory(Base):
    __tablename__ = "card_review_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Ключевое: лог ревью привязываем к уровню
    card_level_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("card_levels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rating: Mapped[str] = mapped_column(
        Enum(ReviewRating, name="review_rating"),
        nullable=False,
    )

    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    show_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reveal_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="review_history")
    card = relationship("Card", back_populates="review_history")
    card_level = relationship("CardLevel", back_populates="review_history")
