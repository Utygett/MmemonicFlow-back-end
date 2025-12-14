from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.card import Card
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings
from app.schemas.card_review import CardForReview, ReviewRequest, ReviewResponse
from app.services.review_service import ReviewService

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
def get_cards_for_review(user_id: str, limit: int = 20, db: Session = Depends(get_db)):
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
        level_content = {}
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
def review_card(card_id: str, request: ReviewRequest, user_id: str, db: Session = Depends(get_db)):
    progress = db.query(CardProgress).filter_by(card_id=card_id, user_id=user_id).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Progress not found")

    card = db.get(Card, card_id)
    settings = db.query(UserLearningSettings).filter_by(user_id=user_id).first()
    if not settings:
        raise HTTPException(status_code=404, detail="User settings not found")

    updated_progress = ReviewService.review(
        card=card,
        progress=progress,
        rating=request.rating,
        user_settings=settings
    )

    db.add(updated_progress)
    db.commit()
    db.refresh(updated_progress)

    return ReviewResponse(
        card_id=card.id,
        next_review=updated_progress.next_review,
        current_level=updated_progress.current_level,
        active_level=updated_progress.active_level,
        streak=updated_progress.streak
    )

# -------------------------------
# Список карточек (с фильтром по deck_id)
# -------------------------------
@router.get("/", response_model=List[dict])
def list_cards(deck_id: Optional[UUID] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Card)
    if deck_id:
        query = query.filter(Card.deck_id == deck_id)
    cards = query.limit(20).all()

    return [
        {
            "id": str(card.id),
            "title": card.title,
            "deck_id": str(card.deck_id),
            "max_level": card.max_level,
        }
        for card in cards
    ]

# -------------------------------
# Прогресс конкретной карточки
# -------------------------------
@router.get("/{card_id}/progress")
def card_progress(card_id: str, db: Session = Depends(get_db)):
    progress = db.query(CardProgress).filter(CardProgress.card_id == card_id).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Progress not found")

    return {
        "card_id": str(progress.card_id),
        "current_level": progress.current_level,
        "streak": progress.streak,
        "next_review": progress.next_review,
    }
