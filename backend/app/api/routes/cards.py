from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.user_study_group_deck import UserStudyGroupDeck
from app.models.user_study_group import UserStudyGroup
from app.schemas.cards import DeckWithCards, CardSummary
from typing import Optional, List
from uuid import UUID
from app.db.session import SessionLocal
from app.models.card import Card
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings
from app.schemas.card_review import CardForReview, ReviewRequest, ReviewResponse
from app.services.review_service import ReviewService
from app.models.card_review_history import CardReviewHistory
from app.models import Deck
from app.models.card_level import CardLevel
from app.schemas.cards import DeckWithCards, CardSummary, CardLevelContent
from app.auth.dependencies import get_current_user_id

router = APIRouter()

# Dependency для базы
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------
# Получение карточек для повторения
# -------------------------------
@router.get("/review", response_model=List[CardForReview])
def get_cards_for_review(user_id: str = Depends(get_current_user_id), limit: int = 20, db: Session = Depends(get_db)):
    progress_list = (
        db.query(CardProgress)
        .filter(CardProgress.user_id == user_id)
        .filter(CardProgress.next_review <= datetime.now(timezone.utc))
        .order_by(CardProgress.next_review.asc())
        .limit(limit)
        .all()
    )

    result = []
    for progress in progress_list:
        card = db.get(Card, progress.card_id)
        level = (
            db.query(CardLevel)
            .filter(
                CardLevel.card_id == card.id,
                CardLevel.level_index == progress.active_level
            )
            .first()
        )
        level_content = level.content if level else {}
        result.append(
            CardForReview(
                card_id=card.id,
                deck_id=card.deck_id,
                title=card.title,
                type=card.type,
                content=level_content,
                current_level=progress.current_level,
                active_level=progress.active_level,
                streak=progress.streak,
                next_review=progress.next_review
            )
        )
    return result

# -------------------------------
# Отправка рейтинга после повторения
# -------------------------------
@router.post("/{card_id}/review", response_model=ReviewResponse)
def review_card(card_id: str, request: ReviewRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # 1. Получаем текущий прогресс
    progress = db.query(CardProgress).filter_by(card_id=card_id, user_id=user_id).first()

    # 1a. Если прогресс не найден — создаём его автоматически
    if not progress:
        progress = CardProgress(
            card_id=card_id,
            user_id=user_id,
            current_level=0,
            active_level=0,
            streak=0,
            last_reviewed=datetime.now(timezone.utc),
            next_review=datetime.now(timezone.utc)
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    if not progress:
        raise HTTPException(status_code=404, detail="Error find or create progress")

    # 2. Получаем карточку
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # 3. Получаем настройки пользователя
    settings = db.query(UserLearningSettings).filter_by(user_id=user_id).first()
    if not settings:
        # Создаём настройки по умолчанию
        settings = UserLearningSettings(
            user_id=user_id,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    if not settings:
        raise HTTPException(status_code=404, detail="Error create or find User settings")

    # 4. Вызываем domain-сервис (чистый)
    from app.services.review_service import ReviewService
    updated_state = ReviewService.review(
        progress=progress,
        rating=request.rating.value  # передаем строку
    )

    # 5. Обновляем прогресс в БД
    progress.current_level = updated_state.current_level
    progress.active_level = updated_state.active_level
    progress.streak = updated_state.streak
    progress.last_reviewed = updated_state.last_reviewed
    progress.next_review = updated_state.next_review
    db.add(progress)

    # 6. Создаём запись в истории повторений
    history_entry = CardReviewHistory(
        user_id=progress.user_id,
        card_id=progress.card_id,
        rating=request.rating,
        interval_minutes=int((progress.next_review - progress.last_reviewed).total_seconds() // 60),
        streak=progress.streak,
        reviewed_at=progress.last_reviewed
    )
    db.add(history_entry)

    # 7. Коммитим изменения
    db.commit()
    db.refresh(progress)

    # 8. Возвращаем результат
    return ReviewResponse(
        card_id=card.id,
        next_review=progress.next_review,
        current_level=progress.current_level,
        active_level=progress.active_level,
        streak=progress.streak
    )


# -------------------------------
# Список колод с карточками, фильтрацией по deck_id, приватности и группам
# -------------------------------
@router.get("/", response_model=List[DeckWithCards])
def list_decks_with_cards(
    user_id: str = Depends(get_current_user_id),
    deck_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    # -------------------------------
    # 1. Собираем доступные колоды
    # -------------------------------
    accessible_deck_ids = set()

    # Публичные колоды
    public_decks = db.query(Deck.id).filter(Deck.is_public == True)
    accessible_deck_ids.update([d.id for d in public_decks])

    # Собственные колоды пользователя
    own_decks = db.query(Deck.id).filter(Deck.owner_id == user_id)
    accessible_deck_ids.update([d.id for d in own_decks])

    # Колоды групп пользователя
    group_decks = (
        db.query(UserStudyGroupDeck.deck_id)
        .join(UserStudyGroup, UserStudyGroupDeck.user_group_id == UserStudyGroup.id)
        .filter(UserStudyGroup.user_id == user_id)
        .all()
    )
    accessible_deck_ids.update([d.deck_id for d in group_decks])

    # Если указан конкретный deck_id, фильтруем
    if deck_id:
        if deck_id in accessible_deck_ids:
            accessible_deck_ids = {deck_id}
        else:
            accessible_deck_ids = set()

    # -------------------------------
    # 2. Берем колоды и карточки
    # -------------------------------
    decks = db.query(Deck).filter(Deck.id.in_(accessible_deck_ids)).all()
    result = []

    for deck in decks:
        cards = db.query(Card).filter(Card.deck_id == deck.id).all()
        card_summaries = []

        for card in cards:
            # Берем все уровни карточки
            levels = db.query(CardLevel).filter(CardLevel.card_id == card.id).all()
            levels_data = [
                CardLevelContent(level_index=l.level_index, content=l.content)
                for l in levels
            ]

            card_summaries.append(
                CardSummary(
                    card_id=card.id,
                    title=card.title,
                    type=card.type,
                    levels=levels_data
                )
            )

        result.append(
            DeckWithCards(
                deck_id=deck.id,
                title=deck.title,
                cards=card_summaries
            )
        )

    return result

@router.post("/{card_id}/level_up")
def level_up(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    progress = db.query(CardProgress).filter_by(card_id=card_id, user_id=user_id).first()
    if not progress:
        raise HTTPException(404, "Progress not found")

    card = db.get(Card, card_id)
    progress.increase_level(max_level=card.max_level)
    db.commit()
    db.refresh(progress)
    return {"active_level": progress.active_level}

@router.post("/{card_id}/level_down")
def level_down(card_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    progress = db.query(CardProgress).filter_by(card_id=card_id, user_id=user_id).first()
    if not progress:
        raise HTTPException(404, "Progress not found")

    progress.decrease_level()
    db.commit()
    db.refresh(progress)
    return {"active_level": progress.active_level}


@router.post("/", response_model=CardSummary)
def create_card(
    deck_id: UUID,
    title: str,
    type: str,
    max_level: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # проверяем, что колода доступна пользователю
    deck = db.query(Deck).filter(
        Deck.id == deck_id,
        (Deck.owner_id == user_id) | (Deck.is_public == True)
    ).first()
    if not deck:
        raise HTTPException(403, "Deck not accessible")

    card = Card(
        deck_id=deck_id,
        title=title,
        type=type,
        max_level=max_level,
    )
    db.add(card)
    db.commit()
    db.refresh(card)

    return CardSummary(
        card_id=card.id,
        title=card.title,
        type=card.type,
        levels=[]
    )

@router.delete("/{card_id}")
def delete_card(card_id: UUID, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = db.query(Card).join(Deck).filter(
        Card.id == card_id,
        Deck.owner_id == user_id
    ).first()
    if not card:
        raise HTTPException(404, "Card not found")

    db.delete(card)
    db.commit()
    return {"status": "ok"}

@router.patch("/{card_id}", response_model=CardSummary)
def update_card(
    card_id: UUID,
    title: Optional[str] = None,
    type: Optional[str] = None,
    max_level: Optional[int] = None,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    card = db.query(Card).join(Deck).filter(
        Card.id == card_id,
        Deck.owner_id == user_id
    ).first()
    if not card:
        raise HTTPException(404, "Card not found")

    if title is not None:
        card.title = title
    if type is not None:
        card.type = type
    if max_level is not None:
        card.max_level = max_level

    db.commit()
    db.refresh(card)

    levels = db.query(CardLevel).filter(CardLevel.card_id == card.id).all()

    return CardSummary(
        card_id=card.id,
        title=card.title,
        type=card.type,
        levels=[
            CardLevelContent(level_index=l.level_index, content=l.content)
            for l in levels
        ]
    )

@router.put("/{card_id}/levels/{level_index}")
def upsert_card_level(
    card_id: UUID,
    level_index: int,
    content: dict,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    card = db.query(Card).join(Deck).filter(
        Card.id == card_id,
        Deck.owner_id == user_id
    ).first()
    if not card:
        raise HTTPException(404, "Card not found")

    level = db.query(CardLevel).filter_by(
        card_id=card_id,
        level_index=level_index
    ).first()

    if level:
        level.content = content
    else:
        level = CardLevel(
            card_id=card_id,
            level_index=level_index,
            content=content
        )
        db.add(level)

    db.commit()
    return {"status": "ok"}

@router.delete("/{card_id}/levels/{level_index}")
def delete_card_level(
    card_id: UUID,
    level_index: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    level = (
        db.query(CardLevel)
        .join(Card)
        .join(Deck)
        .filter(
            CardLevel.card_id == card_id,
            CardLevel.level_index == level_index,
            Deck.owner_id == user_id
        )
        .first()
    )

    if not level:
        raise HTTPException(404, "Level not found")

    db.delete(level)
    db.commit()
    return {"status": "ok"}
