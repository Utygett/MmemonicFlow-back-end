from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class UserStudyGroupDeck(Base):
    __tablename__ = "user_study_group_decks"

    user_group_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_study_groups.id"),
        primary_key=True
    )

    deck_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("decks.id"),
        primary_key=True
    )

    order_index: Mapped[int] = mapped_column(Integer, default=0)
