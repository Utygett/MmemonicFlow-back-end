from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class GroupCreate(BaseModel):
    title: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None


class GroupUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class GroupResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
