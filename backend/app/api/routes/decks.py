from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import SessionLocal
from app.models.user_study_group import UserStudyGroup
from app.models.user_study_group_deck import UserStudyGroupDeck
from app.models.deck import Deck
from app.schemas.cards import DeckSummary
from app.auth.dependencies import get_current_user_id
from app.schemas.cards import CardSummary, CardLevelContent
from app.models.card import Card
from app.models.card_level import CardLevel

router = APIRouter(tags=["decks"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[DeckSummary])
def list_user_decks(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Получить все колоды пользователя (только информация о колоде, без карточек)
    """
    user_groups = db.query(UserStudyGroup).filter(UserStudyGroup.user_id == user_id).all()
    if not user_groups:
        return []

    deck_list = []
    for ug in user_groups:
        user_group_decks = db.query(UserStudyGroupDeck).filter(
            UserStudyGroupDeck.user_group_id == ug.id
        ).all()

        for ugd in user_group_decks:
            deck = db.query(Deck).filter(Deck.id == ugd.deck_id).first()
            if not deck:
                continue

            deck_list.append(DeckSummary(deck_id=deck.id, title=deck.title))

    return deck_list


@router.get("/{deck_id}/cards", response_model=List[CardSummary])
def list_deck_cards(deck_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """
    Получить карточки конкретной колоды с уровнями
    """
    # Проверяем, что колода доступна пользователю через группу
    user_groups = db.query(UserStudyGroup).all()
    user_group_decks = db.query(UserStudyGroupDeck).join(UserStudyGroup).filter(
        UserStudyGroup.user_id == user_id,
        UserStudyGroupDeck.deck_id == deck_id
    ).first()
    if not user_group_decks:
        raise HTTPException(404, "Deck not found or access denied")

    cards = db.query(Card).filter(Card.deck_id == deck_id).all()
    result = []
    for card in cards:
        levels = db.query(CardLevel).filter(CardLevel.card_id == card.id).all()
        levels_data = [
            CardLevelContent(level_index=l.level_index, content=l.content)
            for l in levels
        ]
        result.append(CardSummary(card_id=card.id, title=card.title, type=card.type, levels=levels_data))
    return result
