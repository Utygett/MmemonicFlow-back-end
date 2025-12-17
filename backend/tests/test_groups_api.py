import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.study_group import StudyGroup
from app.models.user_study_group import UserStudyGroup
from app.models.user_study_group_deck import UserStudyGroupDeck
from app.models.deck import Deck
from app.models.card import Card
from app.api.routes.groups import get_db as original_get_db


# -----------------------------
# DB session fixture
# -----------------------------
@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------
# TestClient fixture с override get_db
# -----------------------------
@pytest.fixture
def client_with_db(db):
    app.dependency_overrides[original_get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides = {}


# -----------------------------
# Fixture для пользователя
# -----------------------------
@pytest.fixture
def user(db):
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4()}@example.com",
        password_hash="hashed",
        username="testuser",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    yield u
    db.delete(u)
    db.commit()

@pytest.fixture
def auth_header(client_with_db, user):
    # создаем токен напрямую через login endpoint
    response = client_with_db.post("/auth/login", params={
        "email": user.email,
        "password": "hashed"  # используем пароль из фикстуры
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# -----------------------------
# Тесты CRUD групп
# -----------------------------
def test_create_get_update_delete_group(client_with_db, db, user, auth_header):
    # --- Create ---
    response = client_with_db.post(
        "/groups/",
        params={"user_id": str(user.id)},
        json={"title": "Тестовая группа", "description": "Описание группы"},
        headers=auth_header
    )
    assert response.status_code == 200
    data = response.json()
    group_id = data["id"]
    assert data["title"] == "Тестовая группа"

    # --- Get list ---
    response = client_with_db.get("/groups/", params={"user_id": str(user.id)}, headers=auth_header)
    assert response.status_code == 200
    assert response.status_code == 200
    groups = response.json()
    assert any(g["id"] == group_id for g in groups)

    # --- Get specific ---
    response = client_with_db.get(f"/groups/{group_id}", params={"user_id": str(user.id)}, headers=auth_header)
    assert response.status_code == 200
    assert response.status_code == 200
    group_data = response.json()
    assert group_data["title"] == "Тестовая группа"

    # --- Update ---
    response = client_with_db.patch(
        f"/groups/{group_id}",
        params={"user_id": str(user.id)},
        json={"title": "Новая группа"},
        headers=auth_header
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Новая группа"

    # --- Delete ---
    response = client_with_db.delete(f"/groups/{group_id}", params={"user_id": str(user.id)}, headers=auth_header)
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    # --- Проверяем, что группа удалена из БД ---
    group_in_db = db.query(StudyGroup).filter(StudyGroup.id == group_id).first()
    assert group_in_db is None
    user_group = db.query(UserStudyGroup).filter(UserStudyGroup.source_group_id == group_id).first()
    assert user_group is None


@pytest.fixture
def group_with_deck_and_cards(db, user):
    # --- Создание ---
    group = StudyGroup(
        owner_id=user.id,
        title="Группа для теста",
        description="Описание",
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    user_group = UserStudyGroup(
        user_id=user.id,
        source_group_id=group.id
    )
    db.add(user_group)
    db.commit()
    db.refresh(user_group)

    deck = Deck(
        owner_id=user.id,
        title="Колода тест",
        description="Описание колоды"
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)

    ugd = UserStudyGroupDeck(
        user_group_id=user_group.id,
        deck_id=deck.id
    )
    db.add(ugd)
    db.commit()

    card = Card(
        deck_id=deck.id,
        title="Карточка тест",
        type="basic",
        max_level=5
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    yield group, user_group, deck, card

    # --- Cleanup: удаляем в правильном порядке ---
    db.delete(card)
    db.commit()

    db.delete(ugd)
    db.commit()

    db.delete(deck)
    db.commit()

    db.delete(user_group)
    db.commit()

    db.delete(group)
    db.commit()



def test_get_group_decks(client_with_db, group_with_deck_and_cards, user, auth_header):
    group, _, deck, card = group_with_deck_and_cards

    response = client_with_db.get(f"/groups/{group.id}/decks", params={"user_id": str(user.id)}, headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    deck_data = data[0]
    assert deck_data["deck_id"] == str(deck.id)
    assert len(deck_data["cards"]) == 1
    assert deck_data["cards"][0]["card_id"] == str(card.id)


def test_group_decks_access_denied(client_with_db, group_with_deck_and_cards, auth_header):
    group, _, _, _ = group_with_deck_and_cards
    fake_user_id = str(uuid.uuid4())

    # создаем токен для "фейкового" пользователя
    fake_auth_header = {"Authorization": f"Bearer {fake_user_id}"}

    response = client_with_db.get(
        f"/groups/{group.id}/decks",
        headers=fake_auth_header
    )
    assert response.status_code == 401
