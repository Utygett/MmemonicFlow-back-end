import pytest
from uuid import UUID
from starlette.testclient import TestClient
from app.models import User, Deck, UserStudyGroup, UserStudyGroupDeck
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.core.security import hash_password


class TestGetUserDecks:
    """GET /api/decks/"""

    def test_list_empty_decks(self, client: TestClient, auth_token: str):
        """Пустой список колод."""
        response = client.get(
            "/api/decks/",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_decks_with_data(self, client: TestClient, auth_token: str, db, test_user, user_group):
        """Список колод с данными."""
        deck = Deck(
            owner_id=test_user.id,
            title="Test Deck",
            description="Test Description",
            color="#FF5733",
            is_public=False
        )
        db.add(deck)
        db.flush()

        link = UserStudyGroupDeck(
            user_group_id=user_group.id,
            deck_id=deck.id,
            order_index=0
        )
        db.add(link)
        db.commit()

        response = client.get(
            "/api/decks/",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Test Deck"
        assert UUID(data[0]["deck_id"])

    def test_list_decks_no_auth(self, client: TestClient):
        """Без авторизации возвращается 401."""
        response = client.get("/api/decks/")
        assert response.status_code == 401


class TestCreateDeck:
    """POST /api/decks/"""

    def test_create_deck_success(self, client: TestClient, auth_token: str):
        """Успешно создаём колоду."""
        response = client.post(
            "/api/decks/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "title": "My New Deck",
                "description": "Learning French",
                "color": "#FF5733"
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My New Deck"
        assert UUID(data["deck_id"])

    def test_create_deck_empty_title(self, client: TestClient, auth_token: str):
        """Пустой title вызывает 422."""
        response = client.post(
            "/api/decks/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"title": "   ", "description": ""}
        )
        assert response.status_code == 422

    def test_create_deck_no_auth(self, client: TestClient):
        """Без авторизации возвращается 401."""
        response = client.post(
            "/api/decks/",
            json={"title": "Test", "description": ""}
        )
        assert response.status_code == 401

    def test_create_deck_default_color(self, client: TestClient, auth_token: str):
        """Если color не указан, используется значение по умолчанию."""
        response = client.post(
            "/api/decks/",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"title": "Deck Without Color"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "deck_id" in data


class TestGetDeckCards:
    """GET /api/decks/{deck_id}/cards"""

    def test_get_deck_cards_success(self, client: TestClient, auth_token: str, db, test_user, user_group):
        """Получаем карточки колоды."""
        deck = Deck(
            owner_id=test_user.id,
            title="Test Deck",
            color="#FF5733",
            is_public=False
        )
        db.add(deck)
        db.flush()

        link = UserStudyGroupDeck(
            user_group_id=user_group.id,
            deck_id=deck.id,
            order_index=0
        )
        db.add(link)
        db.flush()

        card = Card(deck_id=deck.id, title="Card 1", type="text", max_level=2)
        db.add(card)
        db.flush()

        level1 = CardLevel(card_id=card.id, level_index=0, content={"question": "Q1", "answer": "A1"})
        level2 = CardLevel(card_id=card.id, level_index=1, content={"question": "Q2", "answer": "A2"})
        db.add_all([level1, level2])
        db.commit()

        response = client.get(
            f"/api/decks/{deck.id}/cards",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Card 1"
        assert len(data[0]["levels"]) == 2

    def test_get_deck_cards_no_access(self, client: TestClient, auth_token: str):
        """Доступ к чужой колоде запрещён."""
        from uuid import uuid4
        fake_deck_id = uuid4()

        response = client.get(
            f"/api/decks/{fake_deck_id}/cards",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404


class TestGetDeckSession:
    """GET /api/decks/{deck_id}/session"""

    def test_get_deck_session_success(self, client: TestClient, auth_token: str, db, test_user):
        """Получаем сессию колоды с карточками и уровнями."""
        deck = Deck(
            owner_id=test_user.id,
            title="Session Deck",
            color="#FF5733",
            is_public=True
        )
        db.add(deck)
        db.flush()

        card1 = Card(deck_id=deck.id, title="Card A", type="text", max_level=1)
        card2 = Card(deck_id=deck.id, title="Card B", type="text", max_level=1)
        db.add_all([card1, card2])
        db.flush()

        level1 = CardLevel(card_id=card1.id, level_index=0, content={"question": "Q1", "answer": "A1"})
        level2 = CardLevel(card_id=card2.id, level_index=0, content={"question": "Q2", "answer": "A2"})
        db.add_all([level1, level2])
        db.commit()

        response = client.get(
            f"/api/decks/{deck.id}/session",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Card A"
        assert data[1]["title"] == "Card B"
        assert len(data[0]["levels"]) == 1

    def test_get_deck_session_creates_progress(self, client: TestClient, auth_token: str, db, test_user):
        """При запросе сессии автоматически создаются прогрессы."""
        deck = Deck(owner_id=test_user.id, title="Session Deck", is_public=True)
        db.add(deck)
        db.flush()

        card = Card(deck_id=deck.id, title="Card", type="text", max_level=1)
        db.add(card)
        db.commit()

        progress_before = db.query(CardProgress).filter(
            CardProgress.card_id == card.id,
            CardProgress.user_id == test_user.id
        ).first()
        assert progress_before is None

        response = client.get(
            f"/api/decks/{deck.id}/session",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200

        progress_after = db.query(CardProgress).filter(
            CardProgress.card_id == card.id,
            CardProgress.user_id == test_user.id
        ).first()
        assert progress_after is not None
        assert progress_after.active_level == 0
        assert progress_after.streak == 0

    def test_get_deck_session_no_access(self, client: TestClient, auth_token: str, db, test_user):
        """Доступ к приватной чужой колоде запрещён."""
        import uuid as uuid_lib
        from app.core.security import hash_password

        # ← Уникальный email каждый раз
        other_user = User(
            username="other",
            email=f"other_{uuid_lib.uuid4()}@example.com",
            password_hash=hash_password("pass")
        )
        db.add(other_user)
        db.flush()

        deck = Deck(
            owner_id=other_user.id,
            title="Private Deck",
            is_public=False
        )
        db.add(deck)
        db.commit()

        response = client.get(
            f"/api/decks/{deck.id}/session",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 403
