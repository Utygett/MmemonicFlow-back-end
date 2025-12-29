from datetime import datetime
from pydantic import BaseModel
from app.core.enums import ReviewRating
from typing import Optional
from uuid import UUID


class CardForReview(BaseModel):
    card_id: UUID
    deck_id: UUID
    title: str
    type: str

    card_level_id: UUID
    level_index: int
    content: dict

    stability: float
    difficulty: float

    next_review: Optional[datetime]


class ReviewRequest(BaseModel):
    rating: ReviewRating


class ReviewResponse(BaseModel):
    card_id: UUID

    card_level_id: UUID
    level_index: int

    stability: float
    difficulty: float
    next_review: datetime
