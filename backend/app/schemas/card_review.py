from datetime import datetime
from pydantic import BaseModel, Field
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
    shown_at: datetime = Field(..., alias="shownAt")
    revealed_at: Optional[datetime] = Field(None, alias="revealedAt")
    rated_at: datetime = Field(..., alias="ratedAt")
    timezone: Optional[str] = None

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True

class ReviewResponse(BaseModel):
    card_id: UUID

    card_level_id: UUID
    level_index: int

    stability: float
    difficulty: float
    next_review: datetime
