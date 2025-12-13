from sqlalchemy import Column, Integer, String, DateTime, JSON
from backend.database import Base
from datetime import datetime

class Card(Base):
    __tablename__ = "cards"

    id = Column(String, primary_key=True, index=True)
    term = Column(String, index=True)
    levels = Column(JSON)  # Список уровней
    current_level = Column(Integer, default=0)
    next_review = Column(DateTime, default=datetime.utcnow)
    streak = Column(Integer, default=0)
    deck_id = Column(String, index=True)
    card_type = Column(String, default="flashcard")
    last_reviewed = Column(DateTime, nullable=True)
