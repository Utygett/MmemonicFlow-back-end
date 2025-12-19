from datetime import datetime, timezone
from uuid import UUID

from fastapi import status
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
from app.schemas.card_review import CardForReview
from app.models import CardProgress
from app.schemas.cards import DeckSessionCard
from app.schemas.cards import DeckSummary, DeckCreate

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


@router.get("/{deck_id}/session", response_model=list[DeckSessionCard])
def get_deck_session(
    deck_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # 1) доступ к колоде
    deck = db.query(Deck).filter(
        Deck.id == deck_id,
        (Deck.owner_id == user_id) | (Deck.is_public == True)
    ).first()
    if not deck:
        raise HTTPException(403, "Deck not accessible")

    # 2) карточки по порядку создания
    cards: List[Card] = (
        db.query(Card)
        .filter(Card.deck_id == deck_id)
        .order_by(Card.created_at.asc())
        .all()
    )

    if not cards:
        return []

    card_ids = [c.id for c in cards]

    # 3) прогресс — одним запросом
    progress_list: List[CardProgress] = (
        db.query(CardProgress)
        .filter(CardProgress.user_id == user_id, CardProgress.card_id.in_(card_ids))
        .all()
    )
    progress_by_card = {p.card_id: p for p in progress_list}

    # 3a) создаём недостающие прогрессы пачкой (1 commit)
    now = datetime.now(timezone.utc)
    to_create: List[CardProgress] = []
    for c in cards:
        if c.id not in progress_by_card:
            p = CardProgress(
                card_id=c.id,
                user_id=user_id,
                current_level=0,
                active_level=0,
                streak=0,
                last_reviewed=now,
                next_review=now,
            )
            to_create.append(p)
            progress_by_card[c.id] = p

    if to_create:
        db.add_all(to_create)
        db.commit()

    # 4) уровни всех карточек — одним запросом
    levels_all: List[CardLevel] = (
        db.query(CardLevel)
        .filter(CardLevel.card_id.in_(card_ids))
        .order_by(CardLevel.card_id.asc(), CardLevel.level_index.asc())
        .all()
    )

    levels_by_card: dict[UUID, List[CardLevel]] = {}
    for lvl in levels_all:
        levels_by_card.setdefault(lvl.card_id, []).append(lvl)

    # 5) собрать ответ
    result: List[DeckSessionCard] = []
    for card in cards:
        progress = progress_by_card[card.id]
        lvls = levels_by_card.get(card.id, [])

        result.append(
            DeckSessionCard(
                card_id=card.id,
                deck_id=card.deck_id,
                title=card.title,
                type=card.type,
                active_level=progress.active_level,
                levels=[CardLevelContent(level_index=l.level_index, content=l.content) for l in lvls],
            )
        )

    return result


@router.post("/", response_model=DeckSummary, status_code=status.HTTP_201_CREATED)
def create_deck(
    payload: DeckCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # важно: в моделях UUID, а get_current_user_id у тебя сейчас отдаёт str
    try:
        user_uuid = UUID(user_id)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user id")

    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")

    # 1) найти любую группу пользователя (у тебя их может быть несколько)
    ug = (
        db.query(UserStudyGroup)
        .filter(UserStudyGroup.user_id == user_uuid)
        .first()
    )

    # 2) если групп нет — создаём одну "личную"
    if not ug:
        ug = UserStudyGroup(user_id=user_uuid, title_override="Мои колоды")
        db.add(ug)
        db.flush()  # чтобы ug.id появился в рамках транзакции

    # 3) создать Deck
    deck = Deck(
        owner_id=user_uuid,
        title=title,
        description=payload.description,
        color=payload.color or "#4A6FA5",
        is_public=False,
    )
    db.add(deck)
    db.flush()  # чтобы deck.id появился

    # 4) привязать Deck к группе (иначе list_user_decks её не вернёт)
    link = UserStudyGroupDeck(
        user_group_id=ug.id,
        deck_id=deck.id,
        order_index=0,
    )
    db.add(link)

    db.commit()

    return DeckSummary(deck_id=deck.id, title=deck.title)
