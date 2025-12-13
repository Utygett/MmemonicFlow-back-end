from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from backend.database import engine, Base, get_db
from backend.models import Card
from typing import List, Optional
from enum import Enum
import uuid
import json

app = FastAPI(
    title="Flashcards API",
    version="1.0.0",
    description="API для системы интервального повторения карточек"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums
class CardType(str, Enum):
    Flashcard = "flashcard"
    Cloze = "cloze"
    MultipleChoice = "multiple-choice"

# Pydantic модели
class CardBase(BaseModel):
    term: str
    levels: List[str]
    deckId: str
    cardType: CardType = CardType.Flashcard

class CardCreate(CardBase):
    pass

class CardUpdate(BaseModel):
    term: Optional[str] = None
    levels: Optional[List[str]] = None
    currentLevel: Optional[int] = None
    nextReview: Optional[datetime] = None
    streak: Optional[int] = None
    deckId: Optional[str] = None
    cardType: Optional[CardType] = None
    lastReviewed: Optional[datetime] = None

class Card(CardBase):
    id: str
    currentLevel: int
    nextReview: datetime
    streak: int
    lastReviewed: Optional[datetime] = None

    class Config:
        from_attributes = True

class DeckBase(BaseModel):
    name: str
    description: str
    color: str = "#4A6FA5"

class DeckCreate(DeckBase):
    pass

class DeckUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cardsCount: Optional[int] = None
    progress: Optional[int] = None
    averageLevel: Optional[float] = None
    color: Optional[str] = None

class Deck(DeckBase):
    id: str
    cardsCount: int
    progress: int
    averageLevel: float

    class Config:
        from_attributes = True

class Achievement(BaseModel):
    id: str
    title: str
    description: str
    icon: str
    unlocked: bool
    progress: Optional[int] = None

class Statistics(BaseModel):
    cardsStudiedToday: int
    timeSpentToday: int
    currentStreak: int
    totalCards: int
    weeklyActivity: List[int]
    achievements: List[Achievement]

class DifficultyRating(str, Enum):
    again = "again"
    hard = "hard"
    good = "good"
    easy = "easy"

class ReviewRequest(BaseModel):
    rating: DifficultyRating

# Хранилище данных в памяти
class Database:
    def __init__(self):
        self.cards = []
        self.decks = []
        self.statistics = {
            "cardsStudiedToday": 24,
            "timeSpentToday": 35,
            "currentStreak": 7,
            "totalCards": 133,
            "weeklyActivity": [15, 22, 18, 25, 20, 24, 19],
            "achievements": [
                {
                    "id": "1",
                    "title": "7 дней",
                    "description": "Недельная серия",
                    "icon": "trophy",
                    "unlocked": True,
                },
                {
                    "id": "2",
                    "title": "100 карточек",
                    "description": "Изучено 100 карточек",
                    "icon": "target",
                    "unlocked": True,
                },
                {
                    "id": "3",
                    "title": "Скорость",
                    "description": "50 карточек за день",
                    "icon": "zap",
                    "unlocked": False,
                },
            ]
        }
        self._init_sample_data()
    
    def _init_sample_data(self):
        # Создаем тестовые колоды
        self.decks = [
            {
                "id": "1",
                "name": "Биология",
                "description": "Основные понятия биологии",
                "cardsCount": 3,
                "progress": 68,
                "averageLevel": 1.5,
                "color": "#4A6FA5",
            },
            {
                "id": "2",
                "name": "История",
                "description": "Важные исторические события",
                "cardsCount": 0,
                "progress": 45,
                "averageLevel": 1.2,
                "color": "#FF9A76",
            },
            {
                "id": "3",
                "name": "Программирование",
                "description": "Основы JavaScript",
                "cardsCount": 0,
                "progress": 82,
                "averageLevel": 2.3,
                "color": "#38A169",
            },
        ]
        
        # Создаем тестовые карточки
        self.cards = [
            {
                "id": "1",
                "term": "Фотосинтез",
                "levels": [
                    "Процесс превращения света в энергию",
                    "Процесс, при котором растения преобразуют световую энергию в химическую, создавая глюкозу из CO₂ и H₂O",
                    "Объясните, почему фотосинтез важен для всей экосистемы планеты",
                    "Сравните световую и темновую фазы фотосинтеза, укажите продукты каждой фазы",
                ],
                "currentLevel": 1,
                "nextReview": datetime.now().isoformat(),
                "streak": 3,
                "deckId": "1",
                "cardType": CardType.Flashcard,
                "lastReviewed": datetime.now().isoformat(),
            },
            {
                "id": "2",
                "term": "Митоз",
                "levels": [
                    "Деление клетки",
                    "Процесс деления соматических клеток, при котором из одной клетки образуются две идентичные",
                    "В чем разница между митозом и мейозом?",
                    "Опишите все фазы митоза и что происходит с хромосомами на каждом этапе",
                ],
                "currentLevel": 0,
                "nextReview": datetime.now().isoformat(),
                "streak": 1,
                "deckId": "1",
                "cardType": CardType.Flashcard,
                "lastReviewed": datetime.now().isoformat(),
            },
            {
                "id": "3",
                "term": "ДНК",
                "levels": [
                    "Носитель генетической информации",
                    "Дезоксирибонуклеиновая кислота - молекула, хранящая генетическую информацию",
                    "Как структура ДНК связана с её функцией?",
                    "Объясните процесс репликации ДНК и роль ферментов в этом процессе",
                ],
                "currentLevel": 2,
                "nextReview": datetime.now().isoformat(),
                "streak": 5,
                "deckId": "1",
                "cardType": CardType.Flashcard,
                "lastReviewed": datetime.now().isoformat(),
            },
        ]

db = Database()

# Вспомогательные функции
def calculate_next_review(current_level: int, streak: int, rating: DifficultyRating) -> datetime:
    """Рассчитывает следующее время повторения на основе SM-2 алгоритма"""
    from datetime import datetime, timedelta
    
    intervals = {
        "again": timedelta(minutes=10),
        "hard": timedelta(hours=6),
        "good": timedelta(days=1),
        "easy": timedelta(days=4)
    }
    
    base_interval = intervals[rating]
    # Увеличиваем интервал в зависимости от уровня и стрика
    multiplier = 1 + (current_level * 0.5) + (streak * 0.1)
    interval = base_interval * multiplier
    
    return datetime.now() + interval

# API Endpoints

# Health check
@app.get("/")
async def root():
    return {"message": "Flashcards API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Карточки
# @app.get("/api/cards", response_model=List[Card])
# async def get_cards(skip: int = 0, limit: int = 100, deck_id: Optional[str] = None):
#     """Получить все карточки с фильтрацией по колоде"""
#     cards = db.cards
#
#     if deck_id:
#         cards = [c for c in cards if c["deckId"] == deck_id]
#
#     return cards[skip:skip + limit]
# Создаём таблицы
Base.metadata.create_all(bind=engine)
# Простой endpoint для проверки
@app.get("/api/cards")
def get_cards(db: Session = Depends(get_db)):
    return db.query(Card).all()



@app.get("/api/cards/{card_id}", response_model=Card)
async def get_card(card_id: str):
    """Получить карточку по ID"""
    for card in db.cards:
        if card["id"] == card_id:
            return card
    raise HTTPException(status_code=404, detail="Card not found")

@app.post("/api/cards", response_model=Card)
async def create_card(card: CardCreate):
    """Создать новую карточку"""
    new_card = {
        "id": str(uuid.uuid4()),
        "term": card.term,
        "levels": card.levels,
        "currentLevel": 0,
        "nextReview": datetime.now().isoformat(),
        "streak": 0,
        "deckId": card.deckId,
        "cardType": card.cardType,
        "lastReviewed": None,
    }
    
    db.cards.append(new_card)
    
    # Обновляем счетчик карточек в колоде
    for deck in db.decks:
        if deck["id"] == card.deckId:
            deck["cardsCount"] += 1
    
    return new_card

@app.put("/api/cards/{card_id}", response_model=Card)
async def update_card(card_id: str, card_update: CardUpdate):
    """Обновить карточку"""
    for i, card in enumerate(db.cards):
        if card["id"] == card_id:
            update_data = card_update.dict(exclude_unset=True)
            
            # Если меняем колоду, обновляем счетчики
            if "deckId" in update_data and update_data["deckId"] != card["deckId"]:
                # Уменьшаем счетчик в старой колоде
                for deck in db.decks:
                    if deck["id"] == card["deckId"]:
                        deck["cardsCount"] = max(0, deck["cardsCount"] - 1)
                # Увеличиваем счетчик в новой колоде
                for deck in db.decks:
                    if deck["id"] == update_data["deckId"]:
                        deck["cardsCount"] += 1
            
            for key, value in update_data.items():
                db.cards[i][key] = value
            
            return db.cards[i]
    
    raise HTTPException(status_code=404, detail="Card not found")

@app.delete("/api/cards/{card_id}")
async def delete_card(card_id: str):
    """Удалить карточку"""
    for i, card in enumerate(db.cards):
        if card["id"] == card_id:
            deleted_card = db.cards.pop(i)
            
            # Уменьшаем счетчик карточек в колоде
            for deck in db.decks:
                if deck["id"] == deleted_card["deckId"]:
                    deck["cardsCount"] = max(0, deck["cardsCount"] - 1)
            
            return {"message": "Card deleted successfully"}
    
    raise HTTPException(status_code=404, detail="Card not found")

@app.post("/api/cards/{card_id}/review")
async def review_card(card_id: str, review: ReviewRequest):
    """Отметить повторение карточки с оценкой сложности"""
    for i, card in enumerate(db.cards):
        if card["id"] == card_id:
            now = datetime.now()
            
            # Обновляем статистику
            db.statistics["cardsStudiedToday"] += 1
            
            # Обновляем карточку
            db.cards[i]["lastReviewed"] = now.isoformat()
            db.cards[i]["streak"] += 1 if review.rating != "again" else 0
            
            # Если ответили правильно (не "again"), увеличиваем уровень
            if review.rating != "again" and db.cards[i]["currentLevel"] < len(db.cards[i]["levels"]) - 1:
                db.cards[i]["currentLevel"] += 1
            
            # Рассчитываем следующее повторение
            next_review = calculate_next_review(
                db.cards[i]["currentLevel"],
                db.cards[i]["streak"],
                review.rating
            )
            db.cards[i]["nextReview"] = next_review.isoformat()
            
            # Обновляем статистику колоды
            for deck in db.decks:
                if deck["id"] == db.cards[i]["deckId"]:
                    # Пересчитываем средний уровень
                    deck_cards = [c for c in db.cards if c["deckId"] == deck["id"]]
                    if deck_cards:
                        deck["averageLevel"] = sum(c["currentLevel"] for c in deck_cards) / len(deck_cards)
                    
                    # Обновляем прогресс (процент карточек выше уровня 0)
                    if deck["cardsCount"] > 0:
                        advanced_cards = sum(1 for c in deck_cards if c["currentLevel"] > 0)
                        deck["progress"] = int((advanced_cards / deck["cardsCount"]) * 100)
            
            return db.cards[i]
    
    raise HTTPException(status_code=404, detail="Card not found")

# Колоды
@app.get("/api/decks", response_model=List[Deck])
async def get_decks(skip: int = 0, limit: int = 100):
    """Получить все колоды"""
    return db.decks[skip:skip + limit]

@app.get("/api/decks/{deck_id}", response_model=Deck)
async def get_deck(deck_id: str):
    """Получить колоду по ID"""
    for deck in db.decks:
        if deck["id"] == deck_id:
            return deck
    raise HTTPException(status_code=404, detail="Deck not found")

@app.post("/api/decks", response_model=Deck)
async def create_deck(deck: DeckCreate):
    """Создать новую колоду"""
    new_deck = {
        "id": str(uuid.uuid4()),
        "name": deck.name,
        "description": deck.description,
        "cardsCount": 0,
        "progress": 0,
        "averageLevel": 0.0,
        "color": deck.color,
    }
    
    db.decks.append(new_deck)
    return new_deck

@app.put("/api/decks/{deck_id}", response_model=Deck)
async def update_deck(deck_id: str, deck_update: DeckUpdate):
    """Обновить колоду"""
    for i, deck in enumerate(db.decks):
        if deck["id"] == deck_id:
            update_data = deck_update.dict(exclude_unset=True)
            for key, value in update_data.items():
                db.decks[i][key] = value
            return db.decks[i]
    
    raise HTTPException(status_code=404, detail="Deck not found")

@app.delete("/api/decks/{deck_id}")
async def delete_deck(deck_id: str):
    """Удалить колоду и все её карточки"""
    for i, deck in enumerate(db.decks):
        if deck["id"] == deck_id:
            # Удаляем все карточки этой колоды
            db.cards = [card for card in db.cards if card["deckId"] != deck_id]
            
            # Удаляем колоду
            db.decks.pop(i)
            
            return {"message": "Deck and its cards deleted successfully"}
    
    raise HTTPException(status_code=404, detail="Deck not found")

@app.get("/api/decks/{deck_id}/cards", response_model=List[Card])
async def get_deck_cards(deck_id: str):
    """Получить все карточки колоды"""
    # Проверяем существование колоды
    deck_exists = any(deck["id"] == deck_id for deck in db.decks)
    if not deck_exists:
        raise HTTPException(status_code=404, detail="Deck not found")
    
    return [card for card in db.cards if card["deckId"] == deck_id]

# Статистика
@app.get("/api/statistics", response_model=Statistics)
async def get_statistics():
    """Получить статистику"""
    return db.statistics

@app.put("/api/statistics")
async def update_statistics(statistics_update: Statistics):
    """Обновить статистику"""
    update_data = statistics_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        db.statistics[key] = value
    return db.statistics

# Карточки для повторения
@app.get("/api/review-cards")
async def get_review_cards(deck_id: Optional[str] = None, limit: int = 20):
    """Получить карточки, готовые к повторению"""
    now = datetime.now()
    review_cards = []
    
    for card in db.cards:
        if deck_id and card["deckId"] != deck_id:
            continue
        
        next_review = datetime.fromisoformat(card["nextReview"].replace('Z', '+00:00'))
        if next_review <= now:
            review_cards.append(card)
    
    # Сортируем по приоритету: сначала давно не повторяемые
    review_cards.sort(key=lambda x: x.get("lastReviewed") or "2000-01-01")
    
    return review_cards[:limit]