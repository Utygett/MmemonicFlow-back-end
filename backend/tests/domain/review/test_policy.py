from datetime import datetime, timedelta

from app.domain.review.entities import CardProgressState
from app.domain.review.policy import ReviewPolicy
from app.core.enums import ReviewRating

from backend.app.domain.review.dto import LearningSettingsSnapshot

settings = LearningSettingsSnapshot(
        base_interval_minutes=60,
        level_factor=0.5,
        streak_factor=0.2,
        again_penalty=0.3,
    )

def test_next_review_is_in_future():
    state = CardProgressState(
        current_level=1,
        active_level=1,
        streak=1,
    )

    policy = ReviewPolicy()
    now = datetime.utcnow()
    next_review = policy.calculate_next_review(
        state=state,
        rating=ReviewRating.good,
        settings=settings,
        now=now,
    )

    assert next_review > now


def test_again_rating_results_in_shorter_interval():
    state = CardProgressState(
        current_level=2,
        active_level=2,
        streak=5,
    )

    policy = ReviewPolicy()
    now = datetime.utcnow()

    next_good = policy.calculate_next_review(
        state=state,
        rating=ReviewRating.good,
        settings=settings,
        now=now,
    )

    next_again = policy.calculate_next_review(
        state=state,
        rating=ReviewRating.again,
        settings=settings,
        now=now,
    )

    assert next_again - now < next_good - now
