from datetime import datetime
from pydantic import BaseModel
from app.core.enums import ReviewRating
from typing import Optional
import uuid

class CardForReview(BaseModel):
    card_id: uuid.UUID
    deck_id: uuid.UUID
    title: str
    type: str
    content: dict
    current_level: int
    active_level: int
    streak: int
    next_review: Optional[datetime]

class ReviewRequest(BaseModel):
    rating: ReviewRating

class ReviewResponse(BaseModel):
    card_id: uuid.UUID
    next_review: datetime
    current_level: int
    active_level: int
    streak: int
