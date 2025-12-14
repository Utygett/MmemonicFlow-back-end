import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings

# -----------------------------
# Создание тестовых данных
# -----------------------------
def populate_test_data(db: Session):
    # --- Пользователь ---
    user = User(
        email="testuser@example.com",
        username="testuser",
        password_hash="hashedpassword"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # --- Настройки обучения ---
    settings = UserLearningSettings(
        user_id=user.id,
        base_interval_minutes=1440,
        level_factor=0.6,
        streak_factor=0.15,
        again_penalty=0.3
    )
    db.add(settings)

    # --- Колода ---
    deck = Deck(
        owner_id=user.id,
        title="Тестовая колода",
        description="Пример колоды для тестирования",
        color="#FF5733",
        is_public=True
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)

    # --- Карточки ---
    cards = []
    for i in range(5):
        card = Card(
            deck_id=deck.id,
            type="basic",
            title=f"Карточка {i+1}",
            max_level=5,
            settings={}
        )
        db.add(card)
        db.commit()
        db.refresh(card)
        cards.append(card)

        # --- Прогресс ---
        progress = CardProgress(
            user_id=user.id,
            card_id=card.id,
            current_level=0,
            active_level=0,
            streak=0,
            next_review=datetime.utcnow() - timedelta(minutes=10),  # чтобы карточки были готовы к повторению
            last_reviewed=None
        )
        db.add(progress)

    db.commit()
    print("Тестовые данные созданы!")

# -----------------------------
# Запуск скрипта
# -----------------------------
if __name__ == "__main__":
    # Инициализация базы
    init_db()

    db = SessionLocal()
    try:
        populate_test_data(db)
    finally:
        db.close()
