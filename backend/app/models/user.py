import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user_learning_settings import UserLearningSettings
    from app.models.card_progress import CardProgress
    from app.models.card_review_history import CardReviewHistory


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String)

    card_progress: Mapped[list["CardProgress"]] = relationship(
        "CardProgress",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    learning_settings: Mapped["UserLearningSettings"] = relationship(
        "UserLearningSettings",
        back_populates="user",
        uselist=False
    )

    review_history: Mapped[list["CardReviewHistory"]] = relationship(
        "CardReviewHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
