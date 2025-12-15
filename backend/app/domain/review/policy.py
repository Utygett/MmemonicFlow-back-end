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
        ReviewRating.again: 0.1,
        ReviewRating.hard: 0.6,
        ReviewRating.good: 1.0,
        ReviewRating.easy: 1.8,
    }

    def calculate_next_review(
            self,
            *,
            state: CardProgressState,
            rating: ReviewRating,
            settings: LearningSettingsSnapshot,
            now: datetime,
    ) -> datetime:
        """
        Возвращает дату следующего повторения.
        """

        # 1. Базовый интервал
        base_interval = timedelta(minutes=settings.base_interval_minutes)

        # 2. Множитель оценки
        rating_multiplier = self.RATING_MULTIPLIERS[rating]

        # 3. Влияние уровня и streak
        level_multiplier = 1 + state.active_level * settings.level_factor
        streak_multiplier = 1 + state.streak * settings.streak_factor

        # 4. Интервал
        interval = (
            base_interval
            * rating_multiplier
            * level_multiplier
            * streak_multiplier
        )

        # 5. Штраф при again
        if rating == ReviewRating.again:
            interval *= settings.again_penalty

        return now + interval
