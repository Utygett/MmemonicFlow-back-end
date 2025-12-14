import uuid
from sqlalchemy import String, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String, default="#4A6FA5")

    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
