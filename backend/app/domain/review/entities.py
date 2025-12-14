# backend/app/domain/review/entities.py

from dataclasses import dataclass
from datetime import datetime
from app.core.enums import ReviewRating


@dataclass
class CardProgressState:
    """
    Чистое domain-состояние прогресса карточки.
    Не знает про БД, ORM и SQLAlchemy.
    """

    current_level: int
    active_level: int
    streak: int
    last_reviewed: datetime | None = None

    # ---------
    # Invariants
    # ---------

    def _validate(self, max_level: int):
        if self.current_level < 0:
            raise ValueError("current_level cannot be negative")

        if self.active_level < 0:
            raise ValueError("active_level cannot be negative")

        if self.active_level > self.current_level:
            raise ValueError("active_level cannot exceed current_level")

        if self.current_level > max_level:
            raise ValueError("current_level cannot exceed max_level")

        if self.streak < 0:
            raise ValueError("streak cannot be negative")

    # ----------------
    # Domain behaviour
    # ----------------

    def apply_rating(
        self,
        *,
        rating: ReviewRating,
        max_level: int,
        reviewed_at: datetime,
    ):
        """
        Применяет результат ответа пользователя к состоянию карточки.
        """

        self.last_reviewed = reviewed_at

        # 1. Стрик
        if rating == ReviewRating.again:
            self.streak = 0
            return

        self.streak += 1

        # 2. Уровни
        if (
            self.active_level == self.current_level
            and self.current_level < max_level
        ):
            self.current_level += 1
            self.active_level = self.current_level

        # 3. Проверка инвариантов
        self._validate(max_level=max_level)
