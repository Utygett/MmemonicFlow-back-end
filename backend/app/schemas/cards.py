from pydantic import BaseModel, Field, ConfigDict, conint
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


class CreateCardLevelOption(BaseModel):
    id: str
    text: str

class CreateCardLevelRequest(BaseModel):
    question: str

    # flashcard
    answer: Optional[str] = None

    # multiple_choice
    options: Optional[List[CreateCardLevelOption]] = None
    correctOptionId: Optional[str] = None
    explanation: Optional[str] = None
    timerSec: Optional[conint(ge=1, le=3600)] = None

class CreateCardRequest(BaseModel):
    deck_id: str
    title: str
    type: str  # или Literal["flashcard","multiple_choice"], если уже готов
    levels: List[CreateCardLevelRequest]


class ReplaceLevelsRequest(BaseModel):
    levels: List[CardLevelPayload]


class DeckSummary(BaseModel):
    deck_id: UUID
    title: str
    description: str | None = None


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


class DeckUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, min_length=1)  # опционально: regex под HEX
    is_public: Optional[bool] = None

class DeckDetail(BaseModel):
    deck_id: UUID = Field(validation_alias="id", serialization_alias="deck_id")
    title: str
    description: Optional[str] = None
    color: str
    owner_id: UUID
    is_public: bool

    model_config = ConfigDict(from_attributes=True)


class DeckWithCards(BaseModel):
    deck: DeckDetail
    cards: List[CardSummary]