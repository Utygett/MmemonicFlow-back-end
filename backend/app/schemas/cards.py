from pydantic import BaseModel, Field, ConfigDict, conint, root_validator
from typing import List, Dict, Optional, Union, Any
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


class QaContentIn(BaseModel):
    question: str
    answer: str


class McqOptionIn(BaseModel):
    id: str
    text: str


class McqContentIn(BaseModel):
    question: str
    options: List[McqOptionIn]
    correctOptionId: str
    explanation: str = ""
    timerSec: conint(ge=0) = 0


ContentIn = Union[QaContentIn, McqContentIn]


class LevelIn(BaseModel):
    level_index: int = Field(ge=0)
    content: ContentIn

    @root_validator(pre=True)
    def parse_content_union(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Payload приходит как:
        {
          "level_index": 0,
          "content": { ... }
        }

        Так как в content нет discriminator-поля (kind/type),
        определяем тип по наличию ключей options/correctOptionId. [web:2]
        """
        c = values.get("content") or {}

        if isinstance(c, dict) and ("options" in c or "correctOptionId" in c):
            values["content"] = McqContentIn(**c)
        else:
            values["content"] = QaContentIn(**c)

        return values


class ReplaceLevelsRequest(BaseModel):
    levels: List[LevelIn]


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

    count_repeat: int = 0
    count_for_repeat: int = 0
    cards_count: int = 0
    completed_cards_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DeckWithCards(BaseModel):
    deck: DeckDetail
    cards: List[CardSummary]