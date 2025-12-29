from dataclasses import dataclass
from datetime import datetime

@dataclass
class CardLevelProgressState:
    stability: float
    difficulty: float
    last_reviewed: datetime | None = None
    next_review: datetime | None = None
