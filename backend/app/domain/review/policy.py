# backend/app/domain/review/policy.py

from datetime import datetime, timedelta
from app.core.enums import ReviewRating

from .dto import LearningSettingsSnapshot
from .entities import CardProgressState


class ReviewPolicy:
    """
    Алгоритм расчёта следующего повторения.
    Чистая domain-логика.
    """

    RATING_MULTIPLIERS = {
        ReviewRating.again: 0.01,
        ReviewRating.hard: 0.6,
        ReviewRating.good: 1.0,
        ReviewRating.easy: 1.8,
    }

    def calculate_next_review(self, *, state, rating, settings, now):
        base_interval = timedelta(minutes=settings.base_interval_minutes)

        # 1. Множитель за текущий streak (ДО этого ответа)
        current_streak_multiplier = 1 + state.streak * settings.streak_factor

        # 2. Множитель за рейтинг
        rating_multiplier = self.RATING_MULTIPLIERS[rating]

        # 3. Множитель за уровень
        level_multiplier = 1 + state.active_level * settings.level_factor

        # 4. Штраф за again
        penalty = settings.again_penalty if rating == ReviewRating.again else 1.0

        # 5. Интервал
        interval = (
                base_interval
                * current_streak_multiplier  # ← используем ТЕКУЩИЙ streak, не будущий!
                * rating_multiplier
                * level_multiplier
                * penalty
        )

        return now + interval
