from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings


class TestGetUserDecks:
    def test_list_empty_decks(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/decks/", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    def test_list_decks_with_data(self, client: TestClient, auth_headers: dict, test_deck):
        resp = client.get("/api/decks/", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Deck"
        assert "deck_id" in data[0]


class TestCreateDeck:
    def test_create_deck_success(self, client: TestClient, auth_headers: dict):
        resp = client.post(
            "/api/decks/",
            headers=auth_headers,
            json={"title": "My New Deck", "description": "Learning French", "color": "#FF5733"},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "My New Deck"
        assert "deck_id" in data

    def test_create_deck_empty_title(self, client: TestClient, auth_headers: dict):
        resp = client.post("/api/decks/", headers=auth_headers, json={"title": "  ", "description": ""})
        assert resp.status_code == 422, resp.text

    def test_create_deck_no_auth(self, client: TestClient):
        resp = client.post("/api/decks/", json={"title": "Test", "description": ""})
        assert resp.status_code == 401, resp.text


class TestGetDeckCards:
    def test_get_deck_cards_success(self, client: TestClient, auth_headers: dict, db, test_deck):
        card = Card(deck_id=test_deck.id, title="Card 1", type="text", max_level=2)
        db.add(card)
        db.flush()

        db.add_all(
            [
                CardLevel(card_id=card.id, level_index=0, content={"question": "Q1", "answer": "A1"}),
                CardLevel(card_id=card.id, level_index=1, content={"question": "Q2", "answer": "A2"}),
            ]
        )
        db.commit()

        resp = client.get(f"/api/decks/{test_deck.id}/cards", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Card 1"
        assert len(data[0]["levels"]) == 2


class TestGetDeckSession:
    def test_get_deck_session_success(self, client: TestClient, auth_headers: dict, db, test_deck, test_user):
        # Настройки нужны для initial_stability/initial_difficulty (их эндпоинт может создать сам,
        # но в тесте проще явно).
        s = db.query(UserLearningSettings).filter_by(user_id=test_user.id).first()
        if not s:
            s = UserLearningSettings(user_id=test_user.id)
            db.add(s)
            db.commit()

        card1 = Card(deck_id=test_deck.id, title="Card A", type="text", max_level=1)
        card2 = Card(deck_id=test_deck.id, title="Card B", type="text", max_level=1)
        db.add_all([card1, card2])
        db.flush()

        lvl1 = CardLevel(card_id=card1.id, level_index=0, content={"question": "Q1", "answer": "A1"})
        lvl2 = CardLevel(card_id=card2.id, level_index=0, content={"question": "Q2", "answer": "A2"})
        db.add_all([lvl1, lvl2])
        db.commit()

        resp = client.get(f"/api/decks/{test_deck.id}/session", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == "Card A"
        assert data[1]["title"] == "Card B"
        assert "active_card_level_id" in data[0]
        assert "active_level_index" in data[0]

        # прогресс должен быть создан для обеих карточек
        p1 = db.query(CardProgress).filter_by(user_id=test_user.id, card_id=card1.id, is_active=True).first()
        p2 = db.query(CardProgress).filter_by(user_id=test_user.id, card_id=card2.id, is_active=True).first()
        assert p1 is not None
        assert p2 is not None

    def test_get_deck_session_creates_progress(self, client: TestClient, auth_headers: dict, db, test_deck, test_user):
        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(lvl0)
        db.commit()

        before = db.query(CardProgress).filter_by(user_id=test_user.id, card_id=card.id, is_active=True).first()
        assert before is None

        resp = client.get(f"/api/decks/{test_deck.id}/session", headers=auth_headers)
        assert resp.status_code == 200, resp.text

        after = db.query(CardProgress).filter_by(user_id=test_user.id, card_id=card.id, is_active=True).first()
        assert after is not None
        assert after.card_level_id == lvl0.id

    def test_review_uses_user_initial_stability(self, client: TestClient, auth_headers: dict, db, test_deck, test_user):
        # задаём кастомные initial_* и проверяем, что они реально используются при первом review
        s = db.query(UserLearningSettings).filter_by(user_id=test_user.id).first()
        if not s:
            s = UserLearningSettings(user_id=test_user.id)
            db.add(s)
            db.flush()

        s.initial_stability = 2.0
        s.initial_difficulty = 5.0
        db.commit()

        card = Card(deck_id=test_deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.flush()

        lvl0 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q", "answer": "A"})
        db.add(lvl0)
        db.commit()

        now = datetime.now(timezone.utc)
        resp = client.post(f"/api/cards/{card.id}/review", headers=auth_headers, json={"rating": "good"})
        assert resp.status_code == 200, resp.text

        # В нашем policy good => stability *= 1.15
        data = resp.json()
        assert float(data["stability"]) == 2.0 * 1.15
        assert data["next_review"]  # просто наличие
        assert datetime.fromisoformat(data["next_review"]).replace(tzinfo=timezone.utc) > now
