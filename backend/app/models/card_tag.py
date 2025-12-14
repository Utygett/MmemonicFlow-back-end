import uuid
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from .card_card_tag import CardCardTag

class CardTag(Base):
    __tablename__ = "card_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    cards = relationship(
        "Card",
        secondary=CardCardTag,
        back_populates="tags"
    )