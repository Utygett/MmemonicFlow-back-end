import uuid
from app.db.session import SessionLocal
from app.models import (
    User,
    Deck,
    Card,
    CardLevel,
    UserStudyGroup,
    UserStudyGroupDeck,
)

USER_EMAIL = "123@email.com"   # 👈 поменяй при необходимости
DECK_TITLE = "Seeded Deck"
CARD_TITLES = [
    "What is Python?",
    "What is FastAPI?",
    "What is SQLAlchemy?",
]

db = SessionLocal()

# -------------------------
# 1️⃣ find user
# -------------------------
user = db.query(User).filter(User.email == USER_EMAIL).first()
assert user, f"User with email {USER_EMAIL} not found"

print("User:", user.id)

# -------------------------
# 2️⃣ get or create user group
# -------------------------
group = (
    db.query(UserStudyGroup)
    .filter(UserStudyGroup.user_id == user.id)
    .first()
)

if not group:
    group = UserStudyGroup(
        id=uuid.uuid4(),
        user_id=user.id,
        title_override="Default Group",
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    print("Created group:", group.id)
else:
    print("Using group:", group.id)

# -------------------------
# 3️⃣ create deck
# -------------------------
deck = Deck(
    id=uuid.uuid4(),
    title=DECK_TITLE,
    owner_id=user.id,
    is_public=True,
)
db.add(deck)
db.commit()
db.refresh(deck)

print("Created deck:", deck.id)

# -------------------------
# 4️⃣ link deck to group
# -------------------------
link = UserStudyGroupDeck(
    user_group_id=group.id,
    deck_id=deck.id,
    order_index=0,
)
db.add(link)
db.commit()

# -------------------------
# 5️⃣ create cards + level 0
# -------------------------
for title in CARD_TITLES:
    card = Card(
        id=uuid.uuid4(),
        deck_id=deck.id,
        title=title,
        type="basic",
        max_level=3,
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    level = CardLevel(
        card_id=card.id,
        level_index=0,
        content={
            "question": title,
            "answer": "TODO",
        },
    )
    db.add(level)
    db.commit()

    print("Added card:", title)

print("\n✅ Deck + cards seeded successfully")
db.close()
