import uuid
from datetime import datetime, timezone
from app.db.session import SessionLocal
from app.models.user import User
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_level import CardLevel

import sys
import os

# Добавляем корень проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_test_deck_for_user(user_email: str):
    db = SessionLocal()
    try:
        # Находим пользователя по email
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            print(f"Пользователь с email={user_email} не найден")
            return

        # 1️⃣ Создаем колоду
        deck = Deck(
            id=uuid.uuid4(),
            title="Тестовая колода",
            owner_id=user.id,
            is_public=True
        )
        db.add(deck)
        db.commit()
        db.refresh(deck)
        print(f"Создана колода: {deck.title} ({deck.id})")

        # 2️⃣ Создаем карточку
        card = Card(
            id=uuid.uuid4(),
            deck_id=deck.id,
            title="Тестовая карточка",
            type="basic",
            max_level=3
        )
        db.add(card)
        db.commit()
        db.refresh(card)
        print(f"Создана карточка: {card.title} ({card.id})")

        # 3️⃣ Создаем уровень карточки
        level = CardLevel(
            card_id=card.id,
            level_index=0,
            content={"question": "Что такое PWA?", "answer": "Progressive Web App"}
        )
        db.add(level)
        db.commit()
        db.refresh(level)
        print(f"Создан уровень для карточки {card.id}: {level.content}")

    finally:
        db.close()


# if __name__ == "__main__":
#     # Подставь email пользователя, для которого создаем колоду
#     create_test_deck_for_user("123@email.com")


from app.db.session import SessionLocal
from app.models.deck import Deck
from uuid import UUID

db = SessionLocal()
user_id = UUID("d52110b6-8cbe-47fa-82e9-27c9a71194e1")  # твой user_id

decks = db.query(Deck).filter(Deck.owner_id == user_id).all()
print("СПИСОК КОЛОД------------")
print(decks)  # должно вывести список колод

db.close()

