from datetime import datetime
import pytest

from app.domain.review.entities import CardProgressState
from app.core.enums import ReviewRating


def test_again_resets_streak_and_does_not_level_up():
    state = CardProgressState(
        current_level=2,
        active_level=2,
        streak=5,
    )

    state.apply_rating(
        rating=ReviewRating.again,
        max_level=5,
        reviewed_at=datetime.utcnow(),
    )

    assert state.streak == 0
    assert state.current_level == 2
    assert state.active_level == 2


def test_good_increases_streak_and_level():
    state = CardProgressState(
        current_level=1,
        active_level=1,
        streak=0,
    )

    state.apply_rating(
        rating=ReviewRating.good,
        max_level=5,
        reviewed_at=datetime.utcnow(),
    )

    assert state.streak == 1
    assert state.current_level == 2
    assert state.active_level == 2


def test_level_does_not_exceed_max_level():
    state = CardProgressState(
        current_level=5,
        active_level=5,
        streak=3,
    )

    state.apply_rating(
        rating=ReviewRating.good,
        max_level=5,
        reviewed_at=datetime.utcnow(),
    )

    assert state.current_level == 5
    assert state.active_level == 5


def test_active_level_never_exceeds_current_level():
    state = CardProgressState(
        current_level=2,
        active_level=2,
        streak=1,
    )

    state.apply_rating(
        rating=ReviewRating.good,
        max_level=3,
        reviewed_at=datetime.utcnow(),
    )

    assert state.active_level <= state.current_level
