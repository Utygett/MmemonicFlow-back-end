import uuid
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from .card_card_tag import CardCardTag



class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    deck_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decks.id")
    )

    type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)

    max_level: Mapped[int] = mapped_column(Integer)

    settings: Mapped[dict | None] = mapped_column(JSONB)

    progress = relationship(
        "CardProgress",
        back_populates="card",
        cascade="all, delete-orphan"
    )

    review_history = relationship(
        "CardReviewHistory",
        back_populates="card",
        cascade="all, delete-orphan"
    )

    tags = relationship(
        "CardTag",
        secondary=CardCardTag,
        back_populates="cards"
    )

    levels = relationship(
        "CardLevel",
        back_populates="card",
        cascade="all, delete-orphan"  # ← ключевой момент
    )