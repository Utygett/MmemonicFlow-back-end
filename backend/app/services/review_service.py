# app/services/review_service.py
from datetime import datetime, timedelta, timezone

class ReviewService:
    @staticmethod
    def review(card, progress, rating, user_settings):
        # rating приходит как строка: 'again', 'hard', 'good', 'easy'
        if rating == "again":
            progress.streak = 0
            interval = user_settings.base_interval_minutes * user_settings.again_penalty
        else:
            progress.streak += 1
            # НЕ трогаем current_level
            interval = user_settings.base_interval_minutes * (
                user_settings.level_factor + user_settings.streak_factor * progress.streak
            )

        progress.next_review = datetime.now(timezone.utc) + timedelta(minutes=interval)
        return progress

