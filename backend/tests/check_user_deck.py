import uuid
from app.db.session import SessionLocal
from app.models.user import User
from app.models.deck import Deck
from app.core.security import hash_password

db = SessionLocal()

# Создаём пользователя
user = User(
    id=uuid.uuid4(),
    email="testuser2@example.com",
    username="testuser2",
    password_hash=hash_password("password123")
)
db.add(user)
db.commit()
db.refresh(user)

# Создаём колоду для пользователя
deck = Deck(
    id=uuid.uuid4(),
    title="SQLAlchemy Test Deck",
    owner_id=user.id,
    is_public=True
)
db.add(deck)
db.commit()
db.refresh(deck)

print("Created deck in DB:", deck)
# Проверяем, что колода видна в базе
user_decks = db.query(Deck).filter(Deck.owner_id == user.id).all()
print("User decks from DB:", user_decks)
