# app/services/review_service.py
from datetime import datetime, timezone
from app.domain.review.entities import CardProgressState
from app.domain.review.policy import ReviewPolicy
from app.core.enums import ReviewRating

class ReviewService:
    @staticmethod
    def review(card, progress, rating: str) -> CardProgressState:
        """
        Чистая domain-логика для обновления прогресса карточки.
        Возвращает новый объект CardProgressState, не взаимодействуя с БД.
        """

        # 1. Преобразуем rating в enum
        try:
            rating_enum = ReviewRating(rating)
        except ValueError:
            raise ValueError(f"Invalid rating: {rating}")

        # 2. Создаём domain-состояние карточки
        state = CardProgressState(
            current_level=progress.current_level,
            active_level=progress.active_level,
            streak=progress.streak,
            last_reviewed=progress.last_reviewed
        )

        # 3. Применяем рейтинг (уровни и стрик)
        state.apply_rating(
            rating=rating_enum,
            max_level=card.max_level,
            reviewed_at=datetime.now(timezone.utc)
        )

        # 4. Рассчитываем next_review через ReviewPolicy
        policy = ReviewPolicy()
        next_review = policy.calculate_next_review(
            state=state,
            rating=rating_enum,
            base_interval_minutes=progress.user.learning_settings.base_interval_minutes,
            level_factor=progress.user.learning_settings.level_factor,
            streak_factor=progress.user.learning_settings.streak_factor,
            again_penalty=progress.user.learning_settings.again_penalty,
            now=datetime.now(timezone.utc)
        )

        # 5. Обновляем поле next_review
        state.next_review = next_review

        return state
