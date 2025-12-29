from datetime import datetime, timezone

from app.core.enums import ReviewRating
from app.domain.review.dto import LearningSettingsSnapshot
from app.domain.review.entities import CardLevelProgressState
from app.domain.review.policy import ReviewPolicy

class ReviewService:
    @staticmethod
    def review(*, progress, rating: str, settings) -> CardLevelProgressState:
        rating_enum = ReviewRating(rating)

        snapshot = LearningSettingsSnapshot(
            desired_retention=settings.desired_retention,
            initial_stability=settings.initial_stability,
            initial_difficulty=settings.initial_difficulty,
            promote_stability_multiplier=settings.promote_stability_multiplier,
            promote_difficulty_delta=settings.promote_difficulty_delta,
        )

        state = CardLevelProgressState(
            stability=progress.stability,
            difficulty=progress.difficulty,
            last_reviewed=progress.last_reviewed,
        )

        now = datetime.now(timezone.utc)
        return ReviewPolicy().apply_review(
            state=state,
            rating=rating_enum,
            settings=snapshot,
            now=now,
        )
