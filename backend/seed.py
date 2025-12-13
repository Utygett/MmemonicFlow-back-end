from backend.database import SessionLocal
from backend.models import Card
from datetime import datetime
import uuid

db = SessionLocal()

test_card = Card(
    id=str(uuid.uuid4()),
    term="Фотосинтез",
    levels=[
        "Процесс превращения света в энергию",
        "Процесс, при котором растения преобразуют световую энергию в химическую, создавая глюкозу из CO₂ и H₂O",
        "Объясните, почему фотосинтез важен для всей экосистемы планеты"
    ],
    current_level=1,
    next_review=datetime.now(),
    streak=3,
    deck_id="1",
    card_type="flashcard",
    last_reviewed=datetime.now()
)

db.add(test_card)
db.commit()
db.close()
print("Тестовая карточка добавлена")
