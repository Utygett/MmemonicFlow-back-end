"""Pytest fixtures - просто и надёжно."""
import os
import pytest
from fastapi.testclient import TestClient
import uuid as uuid_lib
import warnings
import logging

# Отключаем ALL SQLAlchemy логирование
logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)

warnings.filterwarnings("ignore", category=DeprecationWarning)

os.environ["DATABASE_URL"] = "postgresql+psycopg2://flashcards_user:flashcards_pass@localhost:5433/flashcards"

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.deck import Deck
from app.models.user_study_group import UserStudyGroup
from app.models.user_study_group_deck import UserStudyGroupDeck
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.models.card_review_history import CardReviewHistory
from app.core.security import hash_password


@pytest.fixture(scope="function")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
def db():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture(scope="function")
def test_user(db):
    """Создаём юзера, удаляем его в конце."""
    user = User(
        username="testuser",
        email=f"test_{uuid_lib.uuid4()}@example.com",
        password_hash=hash_password("password123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # УДАЛЯЕМ ВСЕ ДАННЫЕ ЭТОГО ЮЗЕРА
    user_id = user.id

    db.query(CardReviewHistory).filter(CardReviewHistory.user_id == user_id).delete()
    db.query(CardProgress).filter(CardProgress.user_id == user_id).delete()

    # Декк айди этого юзера
    deck_ids = [d.id for d in db.query(Deck.id).filter(Deck.owner_id == user_id).all()]

    if deck_ids:
        db.query(CardLevel).filter(
            CardLevel.card_id.in_(
                db.query(Card.id).filter(Card.deck_id.in_(deck_ids))
            )
        ).delete()
        db.query(Card).filter(Card.deck_id.in_(deck_ids)).delete()
        db.query(UserStudyGroupDeck).filter(UserStudyGroupDeck.deck_id.in_(deck_ids)).delete()
        db.query(Deck).filter(Deck.owner_id == user_id).delete()

    db.query(UserStudyGroup).filter(UserStudyGroup.user_id == user_id).delete()
    db.query(User).filter(User.id == user_id).delete()

    db.commit()


@pytest.fixture(scope="function")
def auth_token(client: TestClient, test_user: User):
    response = client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "password123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def user_group(db, test_user: User) -> UserStudyGroup:
    group = UserStudyGroup(user_id=test_user.id, title_override="Test Group")
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@pytest.fixture(scope="function")
def test_deck(db, test_user: User) -> Deck:
    deck = Deck(
        owner_id=test_user.id,
        title="Test Deck",
        color="#FF5733",
        is_public=True
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return deck


@pytest.fixture(scope="function", autouse=True)
def cleanup_auth_users(db):
    """Очищает юзеров из test_auth.py после каждого теста."""
    yield

    # Удаляем юзеров с этими email паттернами (из test_auth.py)
    patterns = [
        "newuser_",
        "duplicate_",
        "login_test_",
        "wrong_pass_",
        "me_test_",
        "refresh_test_",
        "new_token_",
        "other_",
        "test_fc",
    ]

    for pattern in patterns:
        users = db.query(User).filter(User.email.like(f"{pattern}%")).all()
        for user in users:
            user_id = user.id
            db.query(CardReviewHistory).filter(CardReviewHistory.user_id == user_id).delete()
            db.query(CardProgress).filter(CardProgress.user_id == user_id).delete()

            deck_ids = [d.id for d in db.query(Deck.id).filter(Deck.owner_id == user_id).all()]
            if deck_ids:
                db.query(CardLevel).filter(
                    CardLevel.card_id.in_(db.query(Card.id).filter(Card.deck_id.in_(deck_ids)))
                ).delete()
                db.query(Card).filter(Card.deck_id.in_(deck_ids)).delete()
                db.query(UserStudyGroupDeck).filter(UserStudyGroupDeck.deck_id.in_(deck_ids)).delete()
                db.query(Deck).filter(Deck.owner_id == user_id).delete()

            db.query(UserStudyGroup).filter(UserStudyGroup.user_id == user_id).delete()
            db.query(User).filter(User.id == user_id).delete()

    db.commit()
