from dataclasses import replace
from datetime import datetime, timedelta

from app.core.enums import ReviewRating
from .entities import CardLevelProgressState
from .dto import LearningSettingsSnapshot

FIRST_AGAIN_MINUTES = 5

class ReviewPolicy:
    STABILITY_MULT = {
        ReviewRating.again: 0.25,
        ReviewRating.hard: 0.85,
        ReviewRating.good: 1.15,
        ReviewRating.easy: 1.35,
    }

    DIFFICULTY_DELTA = {
        ReviewRating.again: +0.6,
        ReviewRating.hard: +0.15,
        ReviewRating.good: -0.05,
        ReviewRating.easy: -0.15,
    }

    def apply_review(
        self,
        *,
        state: CardLevelProgressState,
        rating: ReviewRating,
        settings: LearningSettingsSnapshot,
        now: datetime,
    ) -> CardLevelProgressState:
        new_difficulty = min(10.0, max(1.0, state.difficulty + self.DIFFICULTY_DELTA[rating]))
        new_stability = max(0.0035, state.stability * self.STABILITY_MULT[rating])  # >= 5 минут (в днях)

        if rating == ReviewRating.again and state.last_reviewed is None:
            next_review = now + timedelta(minutes=FIRST_AGAIN_MINUTES)
        else:
            next_review = now + timedelta(days=new_stability)

        return replace(
            state,
            stability=new_stability,
            difficulty=new_difficulty,
            last_reviewed=now,
            next_review=next_review,
        )
