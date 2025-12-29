import uuid

from sqlalchemy import Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CardLevel(Base):
    __tablename__ = "card_levels"

    __table_args__ = (
        UniqueConstraint("card_id", "level_index", name="uq_card_level_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    level_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)

    card: Mapped["Card"] = relationship("Card", back_populates="levels")

    progress: Mapped[list["CardProgress"]] = relationship(
        "CardProgress",
        back_populates="card_level",
        cascade="all, delete-orphan",
    )

    review_history: Mapped[list["CardReviewHistory"]] = relationship(
        "CardReviewHistory",
        back_populates="card_level",
        cascade="all, delete-orphan",
    )
