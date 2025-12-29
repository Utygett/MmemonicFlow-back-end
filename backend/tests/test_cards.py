from datetime import datetime, timezone, timedelta

from starlette.testclient import TestClient

from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.models.card_review_history import CardReviewHistory

from app.core.enums import ReviewRating
from app.domain.review.policy import ReviewPolicy
from app.domain.review.dto import LearningSettingsSnapshot
from app.domain.review.entities import CardLevelProgressState


class TestLevelUp:
    """POST /api/cards/{card_id}/level_up"""

    def test_level_up_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        # Карточка + уровни
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=3)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q0", "answer": "A0"})
        lvl1 = CardLevel(card_id=card.id, level_index=1, content={"question": "Q1", "answer": "A1"})
        db.add_all([lvl0, lvl1])
        db.commit()

        # В новой логике прогресс может не существовать — эндпоинт сам создаст lvl0-progress и переключит на lvl1
        response = client.post(
            f"/api/cards/{card.id}/level_up",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["active_level_index"] == 1
        assert "active_card_level_id" in data

        active = (
            db.query(CardProgress)
            .filter_by(user_id=test_user.id, card_id=card.id, is_active=True)
            .first()
        )
        assert active is not None
        active_level = db.get(CardLevel, active.card_level_id)
        assert active_level.level_index == 1


class TestLevelDown:
    """POST /api/cards/{card_id}/level_down"""

    def test_level_down_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=3)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q0", "answer": "A0"})
        lvl1 = CardLevel(card_id=card.id, level_index=1, content={"question": "Q1", "answer": "A1"})
        db.add_all([lvl0, lvl1])
        db.commit()

        # Сначала поднимем на 1
        up = client.post(
            f"/api/cards/{card.id}/level_up",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert up.status_code == 200, up.text
        assert up.json()["active_level_index"] == 1

        # Потом опустим на 0
        down = client.post(
            f"/api/cards/{card.id}/level_down",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert down.status_code == 200, down.text
        assert down.json()["active_level_index"] == 0

        active = (
            db.query(CardProgress)
            .filter_by(user_id=test_user.id, card_id=card.id, is_active=True)
            .first()
        )
        assert active is not None
        active_level = db.get(CardLevel, active.card_level_id)
        assert active_level.level_index == 0


class TestReviewCard:
    """POST /api/cards/{card_id}/review"""

    def test_review_card_success(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(lvl0)
        db.commit()

        response = client.post(
            f"/api/cards/{card.id}/review",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"rating": "easy"},
        )
        assert response.status_code == 200, response.text
        data = response.json()

        # новый ответ
        assert "card_id" in data
        assert "card_level_id" in data
        assert "level_index" in data
        assert "stability" in data
        assert "difficulty" in data
        assert "next_review" in data

        # прогресс должен существовать (активный)
        active = (
            db.query(CardProgress)
            .filter_by(user_id=test_user.id, card_id=card.id, is_active=True)
            .first()
        )
        assert active is not None

        # и история review должна быть записана
        h = db.query(CardReviewHistory).filter_by(user_id=test_user.id, card_id=card.id).first()
        assert h is not None
        assert h.card_level_id == active.card_level_id


class TestGetCardsForReview:
    """GET /api/cards/review"""

    def test_get_cards_for_review_empty(self, client: TestClient, auth_token: str):
        response = client.get(
            "/api/cards/review",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == []

    def test_get_cards_for_review_has_due(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(lvl0)
        db.flush()

        now = datetime.now(timezone.utc)
        p = CardProgress(
            user_id=test_user.id,
            card_id=card.id,
            card_level_id=lvl0.id,
            is_active=True,
            stability=1.0,
            difficulty=5.0,
            last_reviewed=now,
            next_review=now - timedelta(minutes=1),  # due
        )
        db.add(p)
        db.commit()

        response = client.get(
            "/api/cards/review",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Card"
        assert data[0]["level_index"] == 0


class TestReviewWithLevels:
    """GET /api/cards/review_with_levels"""

    def test_review_with_levels_empty(self, client: TestClient, auth_token: str):
        response = client.get(
            "/api/cards/review_with_levels",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200, response.text
        assert response.json() == []

    def test_review_with_levels_has_cards(self, client: TestClient, auth_token: str, db, test_user, test_deck):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=2)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q0", "answer": "A0"})
        lvl1 = CardLevel(card_id=card.id, level_index=1, content={"question": "Q1", "answer": "A1"})
        db.add_all([lvl0, lvl1])
        db.flush()

        now = datetime.now(timezone.utc)
        p = CardProgress(
            user_id=test_user.id,
            card_id=card.id,
            card_level_id=lvl0.id,
            is_active=True,
            stability=1.0,
            difficulty=5.0,
            last_reviewed=now,
            next_review=now - timedelta(minutes=1),
        )
        db.add(p)
        db.commit()

        response = client.get(
            "/api/cards/review_with_levels",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()

        assert len(data) == 1
        assert data[0]["title"] == "Card"
        assert data[0]["level_index"] == 0
        assert len(data[0]["levels"]) == 2


class TestReviewPolicy:
    """Unit-тесты доменной логики FSRS-like"""

    def test_apply_review_again(self):
        policy = ReviewPolicy()
        now = datetime.now(timezone.utc)

        settings = LearningSettingsSnapshot(
            desired_retention=0.9,
            initial_stability=1.0,
            initial_difficulty=5.0,
            promote_stability_multiplier=0.85,
            promote_difficulty_delta=0.5,
        )

        state = CardLevelProgressState(stability=4.0, difficulty=5.0)
        updated = policy.apply_review(state=state, rating=ReviewRating.again, settings=settings, now=now)

        assert updated.stability == 4.0 * 0.25
        assert updated.difficulty == 5.0 + 0.6
        assert updated.next_review > now

    def test_apply_review_easy(self):
        policy = ReviewPolicy()
        now = datetime.now(timezone.utc)

        settings = LearningSettingsSnapshot(
            desired_retention=0.9,
            initial_stability=1.0,
            initial_difficulty=5.0,
            promote_stability_multiplier=0.85,
            promote_difficulty_delta=0.5,
        )

        state = CardLevelProgressState(stability=2.0, difficulty=5.0)
        updated = policy.apply_review(state=state, rating=ReviewRating.easy, settings=settings, now=now)

        assert updated.stability == 2.0 * 1.35
        assert updated.difficulty == 5.0 - 0.15
        assert updated.next_review > now
