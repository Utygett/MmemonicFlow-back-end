import pytest
from uuid import UUID
from starlette.testclient import TestClient
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from datetime import datetime, timezone, timedelta
import logging
import sys

# 🔇 УБИВАЕМ ЛОГИРОВАНИЕ SQLALCHEMY В КОРНЕ
for logger_name in ['sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.pool', 'sqlalchemy.orm', 'sqlalchemy.dialects']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.CRITICAL + 1)  # Выше CRITICAL — ничего не пройдет
    logger.handlers = []  # Убираем все handlers

# Дополнительно — отключаем вывод в консоль
logging.disable(logging.CRITICAL)


class TestCreateCard:
    """POST /api/cards/"""

    def test_create_card_success(self, client: TestClient, auth_token: str, db, test_deck):
        response = client.post(
            "/api/cards/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "deck_id": str(test_deck.id),
                "title": "French Greeting",
                "type": "text",
                "levels": [
                    {"question": "Hello", "answer": "Bonjour"},
                    {"question": "Good morning", "answer": "Bon matin"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "French Greeting"
        assert len(data["levels"]) == 2


class TestReplaceLevels:
    """PUT /api/cards/{card_id}/levels"""

    def test_replace_levels_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=2)
        db.add(card)
        db.flush()

        level1 = CardLevel(card_id=card.id, level_index=0, content={"question": "Old Q1", "answer": "Old A1"})
        level2 = CardLevel(card_id=card.id, level_index=1, content={"question": "Old Q2", "answer": "Old A2"})
        db.add_all([level1, level2])
        db.commit()

        response = client.put(
            f"/api/cards/{card.id}/levels",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "levels": [
                    {"question": "New Q1", "answer": "New A1"},
                    {"question": "New Q2", "answer": "New A2"},
                    {"question": "New Q3", "answer": "New A3"}
                ]
            }
        )
        assert response.status_code == 200
        assert response.json()["max_level"] == 3


class TestLevelUp:
    """POST /api/cards/{card_id}/level_up"""

    def test_level_up_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=3)
        db.add(card)
        db.flush()

        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc)
        )
        db.add(progress)
        db.commit()

        response = client.post(
            f"/api/cards/{card.id}/level_up",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert response.json()["active_level"] == 1


class TestLevelDown:
    """POST /api/cards/{card_id}/level_down"""

    def test_level_down_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=3)
        db.add(card)
        db.flush()

        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=2,
            current_level=2,
            streak=0,
            last_reviewed=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc)
        )
        db.add(progress)
        db.commit()

        response = client.post(
            f"/api/cards/{card.id}/level_down",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert response.json()["active_level"] == 1


class TestReviewCard:
    """POST /api/cards/{card_id}/review"""

    def test_review_card_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        level = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level)
        db.flush()

        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc)
        )
        db.add(progress)
        db.commit()

        response = client.post(
            f"/api/cards/{card.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "easy"}
        )
        assert response.status_code == 200
        assert "next_review" in response.json()


class TestGetReviewSession:
    """GET /api/cards/review_with_levels"""

    def test_get_review_session_empty(self, client: TestClient, auth_token: str):
        response = client.get(
            "/api/cards/review_with_levels",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_get_review_session_with_cards(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=2)
        db.add(card)
        db.flush()

        level1 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q1", "answer": "A1"})
        level2 = CardLevel(card_id=card.id, level_index=1, content={"question": "Q2", "answer": "A2"})
        db.add_all([level1, level2])
        db.flush()

        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.add(progress)
        db.commit()

        response = client.get(
            "/api/cards/review_with_levels",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Card"


import pytest
from datetime import datetime, timezone, timedelta
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.core.enums import ReviewRating
from app.domain.review.policy import ReviewPolicy
from app.domain.review.dto import LearningSettingsSnapshot
from app.domain.review.entities import CardProgressState


class TestReviewPolicy:
    """Тестируем domain-логику review алгоритма."""

    def test_again_rating_sets_short_interval(self):
        """При 'again' интервал должен быть очень короткий."""
        policy = ReviewPolicy()

        state = CardProgressState(
            active_level=0,
            current_level=0,
            streak=0
        )

        settings = LearningSettingsSnapshot(
            base_interval_minutes=1,
            level_factor=0.1,
            streak_factor=0.1,
            again_penalty=0.5,
        )

        now = datetime.now(timezone.utc)
        next_review = policy.calculate_next_review(  # ← Без распаковки
            state=state,
            rating=ReviewRating.again,
            settings=settings,
            now=now,
        )

        # 1 минута * 0.1 (again) * 1 (level) * 1 (streak) * 0.5 (penalty) = 0.05 минут = 3 секунды
        expected_interval = timedelta(minutes=1) * 0.1 * 0.5
        expected_next = now + expected_interval

        assert next_review == expected_next

    def test_easy_rating_sets_long_interval(self):
        """При 'easy' интервал должен быть длинный."""
        policy = ReviewPolicy()

        state = CardProgressState(
            active_level=0,
            current_level=0,
            streak=0
        )

        settings = LearningSettingsSnapshot(
            base_interval_minutes=1,
            level_factor=0.1,
            streak_factor=0.1,
            again_penalty=0.5,
        )

        now = datetime.now(timezone.utc)
        next_review = policy.calculate_next_review(
            state=state,
            rating=ReviewRating.easy,
            settings=settings,
            now=now,
        )

        # 1 минута * 1.8 (easy) * 1 (level) * 1 (streak) = 1.8 минут
        expected_interval = timedelta(minutes=1) * 1.8
        expected_next = now + expected_interval

        assert next_review == expected_next

    def test_level_affects_interval(self):
        """Выше уровень = дольше интервал."""
        policy = ReviewPolicy()
        settings = LearningSettingsSnapshot(
            base_interval_minutes=1,
            level_factor=0.1,
            streak_factor=0.1,
            again_penalty=0.5,
        )
        now = datetime.now(timezone.utc)

        # Уровень 0
        state_level0 = CardProgressState(
            active_level=0,
            current_level=0,
            streak=0
        )
        next_review_0 = policy.calculate_next_review(
            state=state_level0,
            rating=ReviewRating.good,
            settings=settings,
            now=now,
        )

        # Уровень 3
        state_level3 = CardProgressState(
            active_level=3,
            current_level=3,
            streak=0
        )
        next_review_3 = policy.calculate_next_review(
            state=state_level3,
            rating=ReviewRating.good,
            settings=settings,
            now=now,
        )

        # Уровень 3 должен иметь больший интервал
        assert next_review_3 > next_review_0

    def test_streak_affects_interval(self):
        """Выше streak = дольше интервал."""
        policy = ReviewPolicy()
        settings = LearningSettingsSnapshot(
            base_interval_minutes=1,
            level_factor=0.1,
            streak_factor=0.1,
            again_penalty=0.5,
        )
        now = datetime.now(timezone.utc)

        # Streak 0
        state_streak0 = CardProgressState(
            active_level=0,
            current_level=0,
            streak=0
        )
        next_review_0 = policy.calculate_next_review(
            state=state_streak0,
            rating=ReviewRating.good,
            settings=settings,
            now=now,
        )

        # Streak 5
        state_streak5 = CardProgressState(
            active_level=0,
            current_level=0,
            streak=5
        )
        next_review_5 = policy.calculate_next_review(
            state=state_streak5,
            rating=ReviewRating.good,
            settings=settings,
            now=now,
        )

        # Streak 5 должен иметь больший интервал
        assert next_review_5 > next_review_0


class TestReviewCardIntegration:
    """Интеграционные тесты review через API."""

    def test_review_card_updates_progress(self, client, auth_token: str, db, test_user, test_deck):
        """После review прогресс должен обновиться."""
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        level = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level)
        db.flush()

        now = datetime.now(timezone.utc)
        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress)
        db.commit()

        # Отправляем review с rating 'easy'
        response = client.post(
            f"/api/cards/{card.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "easy"}
        )

        assert response.status_code == 200
        data = response.json()

        # Парсим datetime и добавляем UTC timezone
        next_review = datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc)
        assert next_review > now

        # Проверяем что streak увеличился
        assert data["streak"] > 0

    def test_review_card_again_resets_streak(self, client, auth_token: str, db, test_user, test_deck):
        """При rating 'again' streak должен сбиться."""
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        level = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level)
        db.flush()

        now = datetime.now(timezone.utc)
        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=5,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress)
        db.commit()

        # Отправляем review с rating 'again'
        response = client.post(
            f"/api/cards/{card.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "again"}
        )

        assert response.status_code == 200
        data = response.json()

        # Streak должен сброситься
        assert data["streak"] == 0

    def test_review_card_easy_longer_interval_than_good(self, client, auth_token: str, db, test_user, test_deck):
        """'easy' должен иметь больший интервал чем 'good'."""
        # Создаём две идентичные карточки
        card1 = Card(deck_id=test_deck.id, title="Card1", type="text", max_level=1)
        card2 = Card(deck_id=test_deck.id, title="Card2", type="text", max_level=1)
        db.add_all([card1, card2])
        db.flush()

        level1 = CardLevel(card_id=card1.id, level_index=0, content={"question": "Q", "answer": "A"})
        level2 = CardLevel(card_id=card2.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add_all([level1, level2])
        db.flush()

        now = datetime.now(timezone.utc)
        progress1 = CardProgress(
            card_id=card1.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        progress2 = CardProgress(
            card_id=card2.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add_all([progress1, progress2])
        db.commit()

        # Review card1 с 'good'
        response1 = client.post(
            f"/api/cards/{card1.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "good"}
        )

        # Review card2 с 'easy'
        response2 = client.post(
            f"/api/cards/{card2.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "easy"}
        )

        next_review_good = datetime.fromisoformat(response1.json()["next_review"]).replace(tzinfo=timezone.utc)
        next_review_easy = datetime.fromisoformat(response2.json()["next_review"]).replace(tzinfo=timezone.utc)

        # 'easy' должен иметь больший интервал
        assert next_review_easy > next_review_good

from app.models import User


class TestReviewWithUserSettings:
    """Тесты review с реальными настройками пользователя из БД."""

    def test_review_uses_user_learning_settings(self, client, auth_token: str, db, test_user, test_deck):
        """Проверяем что review использует настройки из UserLearningSettings."""
        from app.models.user_learning_settings import UserLearningSettings

        custom_settings = UserLearningSettings(
            user_id=test_user.id,
            base_interval_minutes=10,
            level_factor=0.5,
            streak_factor=0.2,
            again_penalty=0.2,
        )
        db.add(custom_settings)
        db.commit()

        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        level = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level)
        db.flush()

        now = datetime.now(timezone.utc)
        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress)
        db.commit()

        response = client.post(
            f"/api/cards/{card.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "good"}
        )

        assert response.status_code == 200
        data = response.json()

        next_review = datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc)
        interval_minutes = (next_review - now).total_seconds() / 60

        assert 8 <= interval_minutes <= 15, f"Expected ~10 minutes, got {interval_minutes}"

    def test_different_users_have_different_intervals(self, client, auth_token: str, db, test_user, test_deck):
        """Разные пользователи должны иметь разные интервалы."""
        from app.models.user_learning_settings import UserLearningSettings
        import uuid as uuid_lib
        from app.core.security import hash_password

        other_user = User(
            username="other_user",
            email=f"other_user_{uuid_lib.uuid4()}@example.com",
            password_hash=hash_password("pass123")
        )
        db.add(other_user)
        db.flush()

        settings1 = UserLearningSettings(
            user_id=test_user.id,
            base_interval_minutes=5,
            level_factor=0.1,
            streak_factor=0.1,
            again_penalty=0.5,
        )

        settings2 = UserLearningSettings(
            user_id=other_user.id,
            base_interval_minutes=60,
            level_factor=0.1,
            streak_factor=0.1,
            again_penalty=0.5,
        )

        db.add_all([settings1, settings2])
        db.commit()

        card1 = Card(deck_id=test_deck.id, title="Card1", type="text", max_level=1)
        db.add(card1)
        db.flush()

        level1 = CardLevel(card_id=card1.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level1)
        db.flush()

        now = datetime.now(timezone.utc)
        progress1 = CardProgress(
            card_id=card1.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress1)
        db.commit()

        auth_response = client.post(
            "/api/auth/login",
            json={"email": other_user.email, "password": "pass123"}
        )
        assert auth_response.status_code == 200, f"Login failed: {auth_response.json()}"
        other_token = auth_response.json()["access_token"]

        card2 = Card(deck_id=test_deck.id, title="Card2", type="text", max_level=1)
        db.add(card2)
        db.flush()

        level2 = CardLevel(card_id=card2.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level2)
        db.flush()

        progress2 = CardProgress(
            card_id=card2.id,
            user_id=other_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress2)
        db.commit()

        response1 = client.post(
            f"/api/cards/{card1.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "good"}
        )

        response2 = client.post(
            f"/api/cards/{card2.id}/review",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"rating": "good"}
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        next_review_1 = datetime.fromisoformat(response1.json()["next_review"]).replace(tzinfo=timezone.utc)
        next_review_2 = datetime.fromisoformat(response2.json()["next_review"]).replace(tzinfo=timezone.utc)

        interval_1 = (next_review_1 - now).total_seconds() / 60
        interval_2 = (next_review_2 - now).total_seconds() / 60

        assert interval_1 < interval_2, f"User 1 ({interval_1}m) should be < User 2 ({interval_2}m)"
        assert interval_1 < 10, f"User 1 interval should be < 10m, got {interval_1}m"
        assert interval_2 > 50, f"User 2 interval should be > 50m, got {interval_2}m"


class TestReviewWithDefaultSettings:
    """Тесты review с дефолтными настройками из БД."""

    def test_default_settings_behavior(self, client, auth_token: str, db, test_user, test_deck):
        """Проверяем поведение с дефолтными настройками."""
        from app.models.user_learning_settings import UserLearningSettings

        # Создаём дефолтные настройки для пользователя
        # (которые автоматически создаются при регистрации)
        default_settings = UserLearningSettings(user_id=test_user.id)
        db.add(default_settings)
        db.commit()

        print(f"Default settings:")
        print(f"  base_interval_minutes: {default_settings.base_interval_minutes}")
        print(f"  level_factor: {default_settings.level_factor}")
        print(f"  streak_factor: {default_settings.streak_factor}")
        print(f"  again_penalty: {default_settings.again_penalty}")

        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        level = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(level)
        db.flush()

        now = datetime.now(timezone.utc)
        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress)
        db.commit()

        response = client.post(
            f"/api/cards/{card.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "good"}
        )

        assert response.status_code == 200
        data = response.json()

        next_review = datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc)
        interval_minutes = (next_review - now).total_seconds() / 60

        print(f"\nWith 'good' rating:")
        print(f"  Interval: {interval_minutes:.2f} minutes")
        print(f"  Next review: {next_review}")

    def test_all_ratings_with_default_settings(self, client, auth_token: str, db, test_user, test_deck):
        """Тестируем все ratings с дефолтными настройками."""
        from app.models.user_learning_settings import UserLearningSettings

        default_settings = UserLearningSettings(user_id=test_user.id)
        db.add(default_settings)
        db.commit()

        print(f"\nDefault settings:")
        print(f"  base_interval: {default_settings.base_interval_minutes} minutes (1440 = 1 day)")
        print(f"  level_factor: {default_settings.level_factor}")
        print(f"  streak_factor: {default_settings.streak_factor}")
        print(f"  again_penalty: {default_settings.again_penalty}")

        ratings = ["again", "hard", "good", "easy"]
        intervals = {}

        now = datetime.now(timezone.utc)

        for rating in ratings:
            card = Card(deck_id=test_deck.id, title=f"Card_{rating}", type="text", max_level=1)
            db.add(card)
            db.flush()

            level = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
            db.add(level)
            db.flush()

            progress = CardProgress(
                card_id=card.id,
                user_id=test_user.id,
                active_level=0,
                current_level=0,
                streak=0,
                last_reviewed=now,
                next_review=now
            )
            db.add(progress)
            db.commit()

            response = client.post(
                f"/api/cards/{card.id}/review",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"rating": rating}
            )

            assert response.status_code == 200
            data = response.json()

            next_review = datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc)
            interval_minutes = (next_review - now).total_seconds() / 60
            intervals[rating] = interval_minutes

        print(f"\nIntervals for each rating:")
        for rating, interval in intervals.items():
            print(f"  {rating}: {interval:.2f} minutes ({interval / 60:.2f} hours, {interval / 1440:.2f} days)")

        # Проверяем что интервалы растут: again < hard < good < easy
        assert intervals["again"] < intervals["hard"]
        assert intervals["hard"] < intervals["good"]
        assert intervals["good"] < intervals["easy"]

    def test_level_impact_with_default_settings(self, client, auth_token: str, db, test_user, test_deck):
        """Как уровень влияет на интервал с дефолтными настройками."""
        from app.models.user_learning_settings import UserLearningSettings

        default_settings = UserLearningSettings(user_id=test_user.id)
        db.add(default_settings)
        db.commit()

        print(f"\nDefault settings:")
        print(f"  base_interval: {default_settings.base_interval_minutes} minutes")
        print(f"  level_factor: {default_settings.level_factor}")

        levels = [0, 1, 3, 5]
        intervals = {}

        now = datetime.now(timezone.utc)

        for lvl in levels:
            card = Card(deck_id=test_deck.id, title=f"Card_level_{lvl}", type="text", max_level=1)
            db.add(card)
            db.flush()

            level_obj = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
            db.add(level_obj)
            db.flush()

            progress = CardProgress(
                card_id=card.id,
                user_id=test_user.id,
                active_level=lvl,
                current_level=lvl,
                streak=0,
                last_reviewed=now,
                next_review=now
            )
            db.add(progress)
            db.commit()

            response = client.post(
                f"/api/cards/{card.id}/review",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"rating": "good"}
            )

            assert response.status_code == 200
            data = response.json()

            next_review = datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc)
            interval_minutes = (next_review - now).total_seconds() / 60
            intervals[lvl] = interval_minutes

        print(f"\nIntervalls for each level (with 'good' rating):")
        for lvl, interval in intervals.items():
            print(f"  Level {lvl}: {interval:.2f} minutes ({interval / 1440:.2f} days)")

        # Проверяем что интервалы растут с уровнем
        assert intervals[0] < intervals[1] < intervals[3] < intervals[5]


import logging
from datetime import datetime, timezone
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings

for logger_name in ['sqlalchemy', 'sqlalchemy.engine', 'sqlalchemy.pool', 'sqlalchemy.orm', 'sqlalchemy.dialects']:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL + 1)
logging.disable(logging.CRITICAL)


class TestReviewScenarios:
    def _run_scenario(self, client, auth_token, db, test_user, test_deck, ratings, title):
        settings = UserLearningSettings(user_id=test_user.id)
        db.add(settings)
        db.commit()

        card = Card(deck_id=test_deck.id, title="TestCard", type="text", max_level=1)
        db.add(card)
        db.flush()

        level = CardLevel(card_id=card.id, level_index=0, content={"q": "Q", "a": "A"})
        db.add(level)
        db.flush()

        now = datetime.now(timezone.utc)
        progress = CardProgress(
            card_id=card.id,
            user_id=test_user.id,
            active_level=0,
            current_level=0,
            streak=0,
            last_reviewed=now,
            next_review=now
        )
        db.add(progress)
        db.commit()

        print(f"\n📊 {title}\n{'=' * 60}")

        for idx, rating in enumerate(ratings):
            response = client.post(
                f"/api/cards/{card.id}/review",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"rating": rating}
            )

            assert response.status_code == 200
            data = response.json()
            next_review = datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc)

            db.refresh(progress)
            # ИСПРАВКА: добавляем timezone к progress.last_reviewed
            last_reviewed = progress.last_reviewed.replace(tzinfo=timezone.utc)
            interval = (next_review - last_reviewed).total_seconds() / 60
            streak = data["streak"]

            print(f"  #{idx + 1} {rating:6} → {interval:7.0f} мин ({interval / 1440:5.2f} дн), streak={streak}")

    def test_scenario_1_consistent_good(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck, ["good"] * 5, "СЦЕНАРИЙ 1: good x5")

    def test_scenario_2_again_hard_recovery(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["again", "again", "hard", "good", "good", "easy", "good"],
                           "СЦЕНАРИЙ 2: again, again, hard, good, good, easy, good")

    def test_scenario_3_forgot_recovery(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["good", "good", "easy", "again", "hard", "good"], "СЦЕНАРИЙ 3: забыл и восстановился")

    def test_scenario_4_hard_learner(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["hard", "hard", "hard", "good", "hard", "good", "good", "good"], "СЦЕНАРИЙ 4: много hard")

    def test_scenario_5_fast_learner(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck, ["good", "easy"] * 3 + ["easy"],
                           "СЦЕНАРИЙ 5: много easy")

    def test_scenario_6_yo_yo(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["good", "easy", "good", "easy", "good", "easy", "easy"], "СЦЕНАРИЙ 6: yo-yo паттерн")

    def test_scenario_7_slow_start(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["again"] * 3 + ["hard"] * 2 + ["good"] * 2 + ["easy"] * 3, "СЦЕНАРИЙ 7: медленный старт")

    def test_scenario_8_mixed(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["hard", "good", "again", "good", "easy", "hard", "good", "easy"],
                           "СЦЕНАРИЙ 8: смешанный паттерн")

    def test_scenario_9_perfect_then_fail(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["good", "good", "easy", "easy", "easy", "again", "good", "good", "good"],
                           "СЦЕНАРИЙ 9: идеально потом забыл")

    def test_scenario_10_chaos(self, client, auth_token: str, db, test_user, test_deck):
        self._run_scenario(client, auth_token, db, test_user, test_deck,
                           ["hard", "again", "easy", "good", "hard", "easy", "again", "good", "easy", "good"],
                           "СЦЕНАРИЙ 10: полный хаос")
