from pydantic import BaseModel
from typing import List, Dict, Optional
from uuid import UUID

class CardLevelContent(BaseModel):
    level_index: int
    content: Dict

class CardSummary(BaseModel):
    card_id: UUID
    title: str
    type: str
    levels: Optional[List[CardLevelContent]] = []

class DeckWithCards(BaseModel):
    deck_id: UUID
    title: str
    cards: List[CardSummary]
