from sqlalchemy import Column, Table, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

CardCardTag = Table(
    "card_card_tag",
    Base.metadata,
    Column("card_id", UUID(as_uuid=True), ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", UUID(as_uuid=True), ForeignKey("card_tags.id", ondelete="CASCADE"), primary_key=True)
)
