import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.models.card import Card
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings
from app.models.deck import Deck
from app.models.user import User
from app.api.routes.cards import get_db as original_get_db

# -----------------------------
# DB session fixture с транзакцией
# -----------------------------
@pytest.fixture
def db():
    db = SessionLocal()
    try:
        # Начинаем nested transaction (savepoint)
        db.begin_nested()
        yield db
        # После теста откатываем изменения
        db.rollback()
    finally:
        db.close()


# -----------------------------
# TestClient с override get_db
# -----------------------------
@pytest.fixture
def client_with_db(db):
    app.dependency_overrides[original_get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides = {}

# -----------------------------
# Fixtures для тестовых данных
# -----------------------------
@pytest.fixture
def user(db):
    u = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4()}@example.com",
        password_hash="hashed",
        username="testuser",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

@pytest.fixture
def deck(db, user):
    d = Deck(
        id=uuid.uuid4(),
        owner_id=user.id,
        title="Тестовая колода",
        description="Описание",
        is_public=True,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d

@pytest.fixture
def card(db, deck):
    c = Card(
        id=uuid.uuid4(),
        title="Тестовая карточка",
        deck_id=deck.id,
        max_level=5,
        type="basic"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

@pytest.fixture
def progress(db, card, user):
    p = CardProgress(
        card_id=card.id,
        user_id=user.id,
        current_level=0,
        active_level=0,
        streak=0,
        next_review=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@pytest.fixture
def user_settings(db, user):
    s = UserLearningSettings(
        user_id=user.id,
        base_interval_minutes=10,
        again_penalty=0.5,
        level_factor=1,
        streak_factor=0.1
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

# -----------------------------
# API тесты
# -----------------------------
def test_list_cards(deck, card, client_with_db):
    response = client_with_db.get(f"/cards/?deck_id={deck.id}")
    assert response.status_code == 200
    data = response.json()
    assert any(c["id"] == str(card.id) for c in data), f"Cards returned: {data}"


def test_card_progress(progress, client_with_db):
    response = client_with_db.get(f"/cards/{progress.card_id}/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["card_id"] == str(progress.card_id)
    assert data["current_level"] == 0
    assert data["streak"] == 0


def test_cards_for_review(user, card, progress, client_with_db):
    response = client_with_db.get(f"/cards/review?user_id={user.id}")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["card_id"] == str(card.id) for c in data)


@pytest.mark.parametrize(
    "rating,expected_streak",
    [
        ("again", 0),
        ("hard", 1),
        ("good", 1),
        ("easy", 1),
    ],
)
def test_review_ratings(card, user, progress, user_settings, rating, expected_streak, client_with_db):
    initial_level = progress.current_level
    response = client_with_db.post(
        f"/cards/{card.id}/review",
        params={"user_id": str(user.id)},
        json={"rating": rating},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_level"] == initial_level
    assert data["streak"] == expected_streak
    assert data["next_review"] is not None
    next_review_dt = datetime.fromisoformat(data["next_review"])
    if next_review_dt.tzinfo is None:
        next_review_dt = next_review_dt.replace(tzinfo=timezone.utc)
    assert next_review_dt > datetime.now(timezone.utc)


def test_review_not_found(user, client_with_db):
    fake_card_id = str(uuid.uuid4())
    response = client_with_db.post(
        f"/cards/{fake_card_id}/review",
        params={"user_id": str(user.id)},
        json={"rating": "good"},
    )
    assert response.status_code == 404
