from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from backend.database import Base


class CardModel(Base):
    __tablename__ = "cards"

    id = Column(String, primary_key=True, index=True)
    term = Column(String, nullable=False)
    levels = Column(JSON, nullable=False)

    current_level = Column(Integer, default=0)
    next_review = Column(DateTime, default=datetime.utcnow)
    streak = Column(Integer, default=0)

    deck_id = Column(String, nullable=False)
    card_type = Column(String, nullable=False)

    last_reviewed = Column(DateTime, nullable=True)
