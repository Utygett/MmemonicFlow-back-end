import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from app.domain.review.entities import CardProgressState
from app.models import CardProgress, Card
from app.main import app
from app.db.session import SessionLocal
from app.models.card import Card
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings
from app.models.deck import Deck
from app.models.user import User
from app.api.routes.cards import get_db as original_get_db
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.db.session import SessionLocal
from sqlalchemy.orm import Session
from app.models.study_group import StudyGroup
from sqlalchemy import text
from app.models.user_study_group import UserStudyGroup
from app.models import CardLevel

# -----------------------------
# DB session fixture
# -----------------------------
@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
        db.rollback()
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
    yield u
    # db.delete(u)
    # db.commit()

# -----------------------------
# JWT Auth fixture
# -----------------------------
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
    yield d
    # db.delete(d)
    # db.commit()


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
    yield c
    # db.delete(c)
    # db.commit()


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
    yield p
    # db.delete(p)
    # db.commit()


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
    yield s
    # db.delete(s)
    # db.commit()

# --- пользователи ---

@pytest.fixture
def other_user(db: Session):
    u = User(
        id=str(uuid.uuid4()),
        email=f"test_{uuid.uuid4()}@example.com",
        username="user2",
        password_hash="hashed_password"
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    yield u
    # db.delete(u)
    # db.commit()

# --- колоды ---
@pytest.fixture
def deck(db: Session, user: User):
    d = Deck(
        id=str(uuid.uuid4()),
        title="Deck 1",
        owner_id=user.id,
        is_public=True  # у тебя public вместо private
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    yield d
    # db.delete(d)
    # db.commit()

@pytest.fixture
def other_deck(db: Session, other_user: User):
    d = Deck(
        id=str(uuid.uuid4()),
        title="Deck 2",
        owner_id=other_user.id,
        is_public=False
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    yield d
    # db.delete(d)
    # db.commit()

# --- карточки ---
@pytest.fixture
def card(db: Session, deck: Deck):
    c = Card(
        id=str(uuid.uuid4()),
        deck_id=deck.id,
        title="Card 1",
        type="basic",
        max_level=3
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    # db.delete(c)
    # db.commit()

@pytest.fixture
def group(db: Session, user: User):
    g = StudyGroup(
        id=str(uuid.uuid4()),
        title="Test Group",
        owner_id=user.id
    )
    db.add(g)
    db.commit()
    db.refresh(g)
    yield g
    # db.delete(g)
    # db.commit()

@pytest.fixture
def user_group(db: Session, user):
    group = UserStudyGroup(
        id=uuid.uuid4(),
        user_id=user.id,  # правильно используем user_id
        title_override="Test Group",
        source_group_id=None,
        parent_id=None
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    yield group
    # db.delete(group)
    # db.commit()

@pytest.fixture
def deck_in_group(db: Session, user_group: UserStudyGroup, user: User):
    d = Deck(
        id=str(uuid.uuid4()),
        title="Deck In Group",
        owner_id=user.id,
        is_public=True
    )
    db.add(d)
    db.commit()
    db.refresh(d)

    # Привязываем к user_study_group
    db.execute(
        text(
            "INSERT INTO user_study_group_decks (user_group_id, deck_id, order_index) "
            "VALUES (:user_group_id, :deck_id, :order_index)"
        ),
        {"user_group_id": user_group.id, "deck_id": d.id, "order_index": 0}
    )
    db.commit()

    yield d

    # Teardown
    db.execute(
        text(
            "DELETE FROM user_study_group_decks WHERE user_group_id = :user_group_id AND deck_id = :deck_id"
        ),
        {"user_group_id": user_group.id, "deck_id": d.id}
    )
    # db.delete(d)
    # db.commit()


@pytest.fixture
def deck_not_in_group(db: Session, other_user: User):
    d = Deck(
        id=str(uuid.uuid4()),
        title="Deck Not In Group",
        owner_id=other_user.id,  # другой пользователь
        is_public=False
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    yield d
    # db.delete(d)
    # db.commit()


# -----------------------------
# API тесты
# -----------------------------
def test_list_cards(deck, card, user, client_with_db, auth_header):
    response = client_with_db.get(
        f"/cards/?deck_id={deck.id}&user_id={user.id}",
        headers=auth_header
    )
    assert response.status_code == 200

    data = response.json()

    assert any(
        c["card_id"] == str(card.id)
        for deck in data
        for c in deck["cards"]
    ), f"Cards returned: {data}"


def test_cards_for_review(user, card, progress, client_with_db, auth_header):
    response = client_with_db.get("/cards/review", headers=auth_header)
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
def test_review_ratings(card, user, progress, user_settings, rating, expected_streak, client_with_db, auth_header):
    initial_level = progress.current_level
    response = client_with_db.post(
        f"/cards/{card.id}/review", headers=auth_header,
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


def test_review_not_found(user, client_with_db, auth_header):
    fake_card_id = str(uuid.uuid4())
    response = client_with_db.post(
        f"/cards/{fake_card_id}/review",
        headers=auth_header,
        params={"user_id": str(user.id)},
        json={"rating": "good"},
    )
    assert response.status_code == 404


# ----------------------------
# 1️⃣ Проверка наличия levels
# ----------------------------
def test_card_levels_present(deck, card, user, client_with_db, auth_header):
    response = client_with_db.get(
        f"/cards/?deck_id={deck.id}&user_id={user.id}",
        headers=auth_header
    )
    assert response.status_code == 200
    data = response.json()

    found = False
    for d in data:
        for c in d["cards"]:
            if c["card_id"] == str(card.id):
                assert "levels" in c, "Card should have 'levels'"
                assert isinstance(c["levels"], list), "'levels' should be a list"
                found = True
    assert found, f"Card {card.id} not found in response"


# ----------------------------
# 2️⃣ Проверка content внутри levels
# ----------------------------
def test_card_levels_content(deck, card, user, client_with_db, auth_header):
    response = client_with_db.get(
        f"/cards/?deck_id={deck.id}&user_id={user.id}",
        headers=auth_header
    )
    data = response.json()

    for d in data:
        for c in d["cards"]:
            if c["card_id"] == str(card.id):
                for level in c["levels"]:
                    assert "content" in level, "Level should have 'content'"
                    assert isinstance(level["content"], dict), "'content' should be a dict"


# ----------------------------
# 3️⃣ Проверка фильтрации по is_public / owner_id
# ----------------------------
def test_only_accessible_decks(deck, other_deck, user, client_with_db, auth_header):
    """
    deck: текущий пользовательский deck
    other_deck: чужая приватная колода
    """
    response = client_with_db.get(f"/cards/?user_id={user.id}", headers=auth_header)
    data = response.json()

    deck_ids = [d["deck_id"] for d in data]

    # Пользователь должен видеть свою колоду
    assert str(deck.id) in deck_ids
    # Не должен видеть чужую приватную колоду
    if not other_deck.is_public:
        assert str(other_deck.id) not in deck_ids


# ----------------------------
# 4️⃣ Проверка фильтрации по группам (если используется)
# ----------------------------
def test_group_filtered_decks(user, group, deck_in_group, deck_not_in_group, client_with_db, auth_header):
    """
    deck_in_group: колода, которая привязана к группе пользователя
    deck_not_in_group: колода, которая НЕ привязана к группе пользователя
    """
    response = client_with_db.get(
        f"/cards/?user_id={user.id}",
        headers=auth_header
    )
    data = response.json()

    deck_ids = [d["deck_id"] for d in data]

    assert str(deck_in_group.id) in deck_ids
    assert str(deck_not_in_group.id) not in deck_ids

def test_cards_for_review_returns_active_level_content(user, card, progress, client_with_db, db, auth_header):
    # 1. Создаём уровень для карточки
    level = CardLevel(
        card_id=card.id,
        level_index=progress.active_level,
        content={"question": "Q", "answer": "A"}
    )
    db.add(level)
    db.commit()

    # 2. Получаем карточки на ревью
    response = client_with_db.get(f"/cards/review?user_id={user.id}", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(c["card_id"] == str(card.id) for c in data)

    # 3. Проверяем, что content соответствует активному уровню
    card_data = next(c for c in data if c["card_id"] == str(card.id))
    assert card_data["content"] == {"question": "Q", "answer": "A"}

@pytest.mark.parametrize(
    "start_level,max_level,expected",
    [
        (0, 3, 1),
        (2, 3, 3),
        (3, 3, 3),  # не выше max_level
    ]
)
def test_level_up(db: Session, start_level, max_level, expected, auth_header):
    # 1️⃣ Создаём пользователя
    user = User(
        id=uuid.uuid4(),
        email=f"user_{uuid.uuid4()}@example.com",
        username=f"user_{uuid.uuid4()}",
        password_hash="hashed"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 2️⃣ Создаём колоду
    deck = Deck(
        id=uuid.uuid4(),
        title="Test Deck",
        owner_id=user.id,
        is_public=True
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)

    # 3️⃣ Создаём карточку
    card = Card(
        id=uuid.uuid4(),
        deck_id=deck.id,
        title="Card",
        type="basic",
        max_level=max_level
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    # 4️⃣ Создаём прогресс
    progress = CardProgress(
        id=uuid.uuid4(),
        user_id=user.id,
        card_id=card.id,
        active_level=start_level,
        current_level=start_level
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)

    # 5️⃣ Поднимаем уровень
    progress.increase_level(max_level=max_level)
    db.commit()
    db.refresh(progress)

    assert progress.active_level == expected


@pytest.mark.parametrize(
    "start_level,expected",
    [
        (3, 2),
        (1, 0),
        (0, 0),  # не ниже 0
    ]
)
def test_level_down(db: Session, start_level, expected):
    # 1️⃣ Создаём пользователя
    user = User(
        id=uuid.uuid4(),
        email=f"user_{uuid.uuid4()}@example.com",
        username=f"user_{uuid.uuid4()}",
        password_hash="hashed"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 2️⃣ Создаём колоду
    deck = Deck(
        id=uuid.uuid4(),
        title="Test Deck",
        owner_id=user.id,
        is_public=True
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)

    # 3️⃣ Создаём карточку
    card = Card(
        id=uuid.uuid4(),
        deck_id=deck.id,
        title="Card",
        type="basic",
        max_level=5
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    # 4️⃣ Создаём прогресс
    progress = CardProgress(
        id=uuid.uuid4(),
        user_id=user.id,
        card_id=card.id,
        active_level=start_level,
        current_level=start_level
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)

    # 5️⃣ Опускаем уровень
    progress.decrease_level()
    db.commit()
    db.refresh(progress)

    assert progress.active_level == expected


@pytest.mark.parametrize(
    "start_level,max_level,expected",
    [
        (0, 3, 1),
        (2, 3, 3),
        (3, 3, 3),
    ]
)
def test_api_level_up(db, client_with_db, card, user, start_level, max_level, expected, auth_header):
    # Проверяем или создаём прогресс
    progress = db.query(CardProgress).filter_by(card_id=card.id, user_id=user.id).first()
    if not progress:
        progress = CardProgress(
            card_id=card.id,
            user_id=user.id,
            current_level=start_level,
            active_level=start_level,
            streak=0,
            next_review=datetime.now(timezone.utc)
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    else:
        progress.active_level = start_level
        card.max_level = max_level
        db.commit()

    response = client_with_db.post(f"/cards/{card.id}/level_up", params={"user_id": str(user.id)}, headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["active_level"] == expected

@pytest.mark.parametrize(
    "start_level,expected",
    [
        (3, 2),
        (1, 0),
        (0, 0),
    ]
)
def test_api_level_down(db, client_with_db, card, user, start_level, expected, auth_header):
    progress = db.query(CardProgress).filter_by(card_id=card.id, user_id=user.id).first()
    if not progress:
        progress = CardProgress(
            card_id=card.id,
            user_id=user.id,
            current_level=start_level,
            active_level=start_level,
            streak=0,
            next_review=datetime.now(timezone.utc)
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    else:
        progress.active_level = start_level
        db.commit()

    response = client_with_db.post(f"/cards/{card.id}/level_down", params={"user_id": str(user.id)}, headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["active_level"] == expected

def test_create_card(deck, user, client_with_db, auth_header):
    response = client_with_db.post(
        "/cards/",
        params={
            "deck_id": deck.id,
            "title": "New Card",
            "type": "basic",
            "max_level": 3,
            "user_id": user.id
        },
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "New Card"
    assert data["type"] == "basic"
    assert data["levels"] == []

def test_create_card_forbidden(other_deck, user, client_with_db, auth_header):
    response = client_with_db.post(
        "/cards/",
        params={
            "deck_id": other_deck.id,
            "title": "Hack Card",
            "type": "basic",
            "max_level": 3,
            "user_id": user.id
        },
        headers=auth_header
    )

    assert response.status_code == 403

def test_update_card(card, user, client_with_db, auth_header):
    response = client_with_db.patch(
        f"/cards/{card.id}",
        params={
            "title": "Updated Title",
            "max_level": 10,
            "user_id": user.id
        },
        headers=auth_header
    )

    assert response.status_code == 200
    data = response.json()

    assert data["title"] == "Updated Title"

def test_update_card_not_owner(card, other_user, client_with_db, auth_header):
    response = client_with_db.patch(
        f"/cards/{card.id}",
        params={
            "title": "Hack",
            "user_id": other_user.id
        }

    )
    assert response.status_code == 401


def test_delete_card(card, client_with_db, db, auth_header):
    # Сохраняем ID перед тестом
    card_id = str(card.id)

    response = client_with_db.delete(
        f"/cards/{card_id}",
        headers=auth_header  # токен передается здесь
    )

    assert response.status_code == 200

    # Проверяем, что карточка действительно удалена
    deleted_card = db.query(Card).filter(Card.id == card_id).first()
    assert deleted_card is None

def test_create_card_level(card, user, client_with_db, db, auth_header):
    response = client_with_db.put(
        f"/cards/{card.id}/levels/0",
        params={"user_id": user.id},
        json={"question": "Q1", "answer": "A1"},
        headers=auth_header
    )

    assert response.status_code == 200

    level = db.query(CardLevel).filter_by(card_id=card.id, level_index=0).first()
    assert level is not None
    assert level.content["question"] == "Q1"

def test_update_card_level(card, user, client_with_db, db, auth_header):
    # создаём уровень
    level = CardLevel(
        card_id=card.id,
        level_index=1,
        content={"question": "Old"}
    )
    db.add(level)
    db.commit()

    response = client_with_db.put(
        f"/cards/{card.id}/levels/1",
        params={"user_id": user.id},
        json={"question": "New"},
        headers=auth_header
    )

    assert response.status_code == 200

    db.refresh(level)
    assert level.content["question"] == "New"

def test_delete_card_level(card, user, client_with_db, db, auth_header):
    level = CardLevel(
        card_id=card.id,
        level_index=2,
        content={"q": "Q"}
    )
    db.add(level)
    db.commit()

    response = client_with_db.delete(
        f"/cards/{card.id}/levels/2",
        params={"user_id": user.id},
        headers=auth_header
    )

    assert response.status_code == 200

    deleted = db.query(CardLevel).filter_by(card_id=card.id, level_index=2).first()
    assert deleted is None

def test_delete_card_level_not_found(card, user, client_with_db, auth_header):
    response = client_with_db.delete(
        f"/cards/{card.id}/levels/999",
        params={"user_id": user.id},
        headers=auth_header
    )

    assert response.status_code == 404
