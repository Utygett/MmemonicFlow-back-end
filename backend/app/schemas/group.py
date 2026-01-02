from enum import Enum
from typing import Optional
from pydantic import BaseModel
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

class CardSummary(BaseModel):
    card_id: UUID
    title: str
    type: str

class GroupKind(str, Enum):
    personal = "personal"         # личная папка
    subscription = "subscription" # подписка на общую группу

class UserGroupResponse(BaseModel):
    user_group_id: UUID
    kind: GroupKind
    source_group_id: Optional[UUID] = None

    title: str
    description: Optional[str] = None

    # Важно: parent_id должен быть "пользовательский", т.е. ссылаться на другие user_group_id
    parent_id: Optional[UUID] = None