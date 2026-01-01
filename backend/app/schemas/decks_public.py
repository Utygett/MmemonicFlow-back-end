# app/schemas/decks_public.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID


class PublicDeckSummary(BaseModel):
    deck_id: UUID
    title: str
    description: Optional[str] = None
    color: Optional[str] = None
    owner_id: UUID

    model_config = ConfigDict(from_attributes=True)
