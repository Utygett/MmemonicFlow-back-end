# app/services/review_service.py
from datetime import datetime, timedelta

class ReviewService:
    @staticmethod
    def review(card, progress, rating, user_settings):
        """
        Обновляет прогресс карточки на основе рейтинга и настроек пользователя.
        """
        # Простая логика: увеличиваем уровень и рассчитываем next_review
        # rating: 0=again, 1=hard, 2=good, 3=easy
        if rating == 0:  # again
            progress.streak = 0
            interval = user_settings.base_interval_minutes * user_settings.again_penalty
        else:
            progress.streak += 1
            interval = user_settings.base_interval_minutes * (user_settings.level_factor + user_settings.streak_factor * progress.streak)

        progress.current_level = min(progress.current_level + 1, card.max_level)
        progress.active_level = progress.current_level
        progress.next_review = datetime.utcnow() + timedelta(minutes=interval)

        return progress
