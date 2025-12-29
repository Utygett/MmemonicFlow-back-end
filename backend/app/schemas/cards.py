from pydantic import BaseModel
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime


class CardLevelContent(BaseModel):
    level_index: int
    content: Dict


class CardForReviewWithLevels(BaseModel):
    card_id: UUID
    deck_id: UUID
    title: str
    type: str

    card_level_id: UUID
    level_index: int
    content: dict

    stability: float
    difficulty: float
    next_review: datetime

    levels: List[CardLevelContent]


class CardSummary(BaseModel):
    card_id: UUID
    title: str
    type: str
    levels: Optional[List[CardLevelContent]] = []


class CardLevelPayload(BaseModel):
    question: str
    answer: str


class CreateCardRequest(BaseModel):
    deck_id: UUID
    title: str
    type: str
    levels: List[CardLevelPayload]


class ReplaceLevelsRequest(BaseModel):
    levels: List[CardLevelPayload]


class DeckWithCards(BaseModel):
    deck_id: UUID
    title: str
    cards: List[CardSummary]


class DeckSummary(BaseModel):
    deck_id: UUID
    title: str


class DeckSessionCard(BaseModel):
    card_id: UUID
    deck_id: UUID
    title: str
    type: str

    active_card_level_id: UUID
    active_level_index: int

    levels: List[CardLevelContent]


class DeckCreate(BaseModel):
    title: str
    description: str | None = None
    color: str | None = None

class CreateCardResponse(BaseModel):
    card_id: UUID
    deck_id: UUID