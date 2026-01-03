from datetime import datetime, timezone
import random
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import asc
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import SessionLocal
from app.auth.dependencies import get_current_user_id
from app.models.deck import Deck
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.models.user_learning_settings import UserLearningSettings
from app.schemas.cards import DeckSummary, CardSummary, CardLevelContent, DeckSessionCard, DeckCreate
from app.models.user_study_group import UserStudyGroup
from app.models.user_study_group_deck import UserStudyGroupDeck
from app.schemas.cards import DeckWithCards
from app.schemas.decks_public import PublicDeckSummary
from app.schemas.cards import DeckDetail, DeckUpdate

router = APIRouter(tags=["decks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_settings(db: Session, user_id: UUID) -> UserLearningSettings:
    s = db.query(UserLearningSettings).filter_by(user_id=user_id).first()
    if s:
        return s
    s = UserLearningSettings(user_id=user_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s








@router.get("/public", response_model=List[PublicDeckSummary])
def search_public_decks(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Deck).filter(Deck.is_public == True)

    if q is not None and q.strip():
        query = query.filter(Deck.title.ilike(f"%{q.strip()}%"))

    decks = (
        query.order_by(asc(Deck.title), asc(Deck.id))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        PublicDeckSummary(
            deck_id=d.id,
            title=d.title,
            description=d.description,
            color=d.color,
            owner_id=d.owner_id,
        )
        for d in decks
    ]


@router.get("/", response_model=List[DeckSummary])
def list_user_decks(user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = user_id

    user_groups = db.query(UserStudyGroup).filter(UserStudyGroup.user_id == user_uuid).all()
    if not user_groups:
        return []

    deck_list = []
    for ug in user_groups:
        links = db.query(UserStudyGroupDeck).filter(UserStudyGroupDeck.user_group_id == ug.id).all()
        for link in links:
            deck = db.query(Deck).filter(Deck.id == link.deck_id).first()
            if deck:
                deck_list.append(DeckSummary(deck_id=deck.id, title=deck.title))
    return deck_list


@router.get("/{deck_id}/cards", response_model=List[CardSummary])
def list_deck_cards(deck_id: UUID, user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    user_uuid = user_id

    link = (
        db.query(UserStudyGroupDeck)
        .join(UserStudyGroup)
        .filter(UserStudyGroup.user_id == user_uuid, UserStudyGroupDeck.deck_id == deck_id)
        .first()
    )
    if not link:
        raise HTTPException(404, "Deck not found or access denied")

    cards = db.query(Card).filter(Card.deck_id == deck_id).all()
    result = []
    for card in cards:
        levels = db.query(CardLevel).filter(CardLevel.card_id == card.id).all()
        levels_data = [CardLevelContent(level_index=l.level_index, content=l.content) for l in levels]
        result.append(CardSummary(card_id=card.id, title=card.title, type=card.type, levels=levels_data))
    return result


@router.get("/{deck_id}/session", response_model=list[DeckSessionCard])
def get_deck_session(
    deck_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_uuid = user_id
    settings = _ensure_settings(db, user_uuid)

    deck = db.query(Deck).filter(
        Deck.id == deck_id,
        (Deck.owner_id == user_uuid) | (Deck.is_public == True)
    ).first()
    if not deck:
        raise HTTPException(403, "Deck not accessible")

    cards: List[Card] = (
        db.query(Card)
        .filter(Card.deck_id == deck_id)
        .order_by(Card.created_at.asc())
        .all()
    )
    if not cards:
        return []

    card_ids = [c.id for c in cards]

    # Берём активный прогресс по карточкам
    progress_list: List[CardProgress] = (
        db.query(CardProgress)
        .filter(
            CardProgress.user_id == user_uuid,
            CardProgress.card_id.in_(card_ids),
            CardProgress.is_active == True,
        )
        .all()
    )
    progress_by_card = {p.card_id: p for p in progress_list}

    # Создаём отсутствующие активные прогрессы на level0
    now = datetime.now(timezone.utc)
    to_create: list[CardProgress] = []

    # Чтобы не делать N+1 за level0, можно одним запросом взять все level0:
    lvl0_all = (
        db.query(CardLevel)
        .filter(CardLevel.card_id.in_(card_ids), CardLevel.level_index == 0)
        .all()
    )
    lvl0_by_card = {l.card_id: l for l in lvl0_all}

    for c in cards:
        if c.id in progress_by_card:
            continue
        lvl0 = lvl0_by_card.get(c.id)
        if not lvl0:
            continue

        p = CardProgress(
            user_id=user_uuid,
            card_id=c.id,
            card_level_id=lvl0.id,
            is_active=True,
            stability=settings.initial_stability,
            difficulty=settings.initial_difficulty,
            last_reviewed=now,
            next_review=now,
        )
        to_create.append(p)
        progress_by_card[c.id] = p

    if to_create:
        db.add_all(to_create)
        db.commit()

    # уровни пачкой
    levels_all: List[CardLevel] = (
        db.query(CardLevel)
        .filter(CardLevel.card_id.in_(card_ids))
        .order_by(CardLevel.card_id.asc(), CardLevel.level_index.asc())
        .all()
    )
    levels_by_card: dict[UUID, List[CardLevel]] = {}
    for lvl in levels_all:
        levels_by_card.setdefault(lvl.card_id, []).append(lvl)

    # собрать ответ
    result: List[DeckSessionCard] = []
    for card in cards:
        progress = progress_by_card[card.id]
        active_level = db.get(CardLevel, progress.card_level_id)
        lvls = levels_by_card.get(card.id, [])

        result.append(
            DeckSessionCard(
                card_id=card.id,
                deck_id=card.deck_id,
                title=card.title,
                type=card.type,
                active_card_level_id=active_level.id,
                active_level_index=active_level.level_index,
                levels=[CardLevelContent(level_index=l.level_index, content=l.content) for l in lvls],
            )
        )
    return result


@router.post("/", response_model=DeckSummary, status_code=status.HTTP_201_CREATED)
def create_deck(
    payload: DeckCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_uuid = user_id

    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")

    ug = db.query(UserStudyGroup).filter(UserStudyGroup.user_id == user_uuid).first()
    if not ug:
        ug = UserStudyGroup(user_id=user_uuid, title_override="Мои колоды")
        db.add(ug)
        db.flush()

    deck = Deck(
        owner_id=user_uuid,
        title=title,
        description=payload.description,
        color=payload.color or "#4A6FA5",
        is_public=False,
    )
    db.add(deck)
    db.flush()

    link = UserStudyGroupDeck(
        user_group_id=ug.id,
        deck_id=deck.id,
        order_index=0,
    )
    db.add(link)

    db.commit()
    return DeckSummary(deck_id=deck.id, title=deck.title)

@router.get("/{deck_id}", response_model=DeckWithCards)
def get_deck_with_cards(
    deck_id: UUID,
    userid: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # доступ как в listdeckcards: через линк user->group->deck [file:151]
    link = (
        db.query(UserStudyGroupDeck)
        .join(UserStudyGroup)
        .filter(UserStudyGroup.user_id == userid, UserStudyGroupDeck.deck_id == deck_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Deck not found or access denied")

    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    cards = db.query(Card).filter(Card.deck_id == deck_id).all()
    result_cards = []
    for card in cards:
        levels = db.query(CardLevel).filter(CardLevel.card_id == card.id).all()
        result_cards.append(
            CardSummary(
                card_id=card.id,
                title=card.title,
                type=card.type,
                levels=[CardLevelContent(level_index=l.level_index, content=l.content) for l in levels],
            )
        )

    return DeckWithCards(deck=deck, cards=result_cards)


@router.get("/{deck_id}/with_cards", response_model=DeckWithCards)
def get_deck_with_cards(
    deck_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    link = (
        db.query(UserStudyGroupDeck)
        .join(UserStudyGroup)
        .filter(UserStudyGroup.user_id == user_id, UserStudyGroupDeck.deck_id == deck_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Deck not found or access denied")

    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    cards = db.query(Card).filter(Card.deck_id == deck_id).all()

    out_cards = []
    for c in cards:
        levels = (
            db.query(CardLevel)
            .filter(CardLevel.card_id == c.id)
            .order_by(CardLevel.level_index.asc())
            .all()
        )
        out_cards.append(
            CardSummary(
                card_id=c.id,
                title=c.title,
                type=c.type,
                levels=[CardLevelContent(level_index=l.level_index, content=l.content) for l in levels],
            )
        )

    return DeckWithCards(deck=deck, cards=out_cards)

@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(
    deck_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    deck = db.get(Deck, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    if str(deck.owner_id) != str(user_id):
        raise HTTPException(status_code=403, detail="You are not the owner of this deck")

    # Удаляем все привязки колоды к user-группам (иначе FK может мешать)
    db.query(UserStudyGroupDeck).filter(UserStudyGroupDeck.deck_id == deck_id).delete(
        synchronize_session=False
    )

    # Удаляем карточки колоды (а дальше БД каскадом удалит уровни/прогресс/историю)
    db.query(Card).filter(Card.deck_id == deck_id).delete(synchronize_session=False)

    # Удаляем саму колоду
    db.delete(deck)
    db.commit()
    return


@router.patch(
    "/{deck_id:uuid}",
    response_model=DeckDetail,
)
def update_deck(
    deck_id: UUID,
    payload: DeckUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    if deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Deck not accessible")

    if payload.title is not None:
        t = payload.title.strip()
        if not t:
            raise HTTPException(status_code=422, detail="Title is required")
        deck.title = t

    if payload.description is not None:
        deck.description = payload.description.strip() if payload.description is not None else None

    if payload.color is not None:
        c = payload.color.strip()
        if not c:
            raise HTTPException(status_code=422, detail="Color is required")
        deck.color = c

    if payload.is_public is not None:
        deck.is_public = payload.is_public

    db.commit()
    db.refresh(deck)

    return DeckDetail(
        id=deck.id,
        title=deck.title,
        description=deck.description,
        color=deck.color,
        owner_id=deck.owner_id,
        is_public=deck.is_public,
    )


@router.get("/{deck_id}/study-cards")
def get_study_cards(
    deck_id: UUID,
    mode: str = Query(..., pattern="^(random|ordered|new_random|new_ordered)$"),
    include: str = Query("full"),
    limit: Optional[int] = Query(default=None, ge=1, le=200),
    seed: Optional[int] = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if include != "full":
        raise HTTPException(status_code=422, detail="Only include=full is supported")

    # доступ как в /session: owner или public
    deck = db.query(Deck).filter(
        Deck.id == deck_id,
        (Deck.owner_id == user_id) | (Deck.is_public == True)
    ).first()
    if not deck:
        raise HTTPException(status_code=403, detail="Deck not accessible")

    cards: List[Card] = (
        db.query(Card)
        .filter(Card.deck_id == deck_id)
        .order_by(Card.created_at.asc())
        .all()
    )
    if not cards:
        return {"cards": []}

    # Для new_*: исключаем все карточки, у которых уже есть хоть какой-то прогресс
    if mode in ("new_random", "new_ordered"):
        all_ids = [c.id for c in cards]
        progressed_ids = {
            row[0]
            for row in (
                db.query(CardProgress.card_id)
                .filter(CardProgress.user_id == user_id, CardProgress.card_id.in_(all_ids))
                .distinct()
                .all()
            )
        }
        cards = [c for c in cards if c.id not in progressed_ids]

    # random / new_random: перемешиваем (seed делает это детерминированно)
    if mode in ("random", "new_random"):
        rnd = random.Random(seed) if seed is not None else random.Random()
        rnd.shuffle(cards)

    # limit после финального порядка
    if limit is not None:
        cards = cards[:limit]

    if not cards:
        return {"cards": []}

    card_ids = [c.id for c in cards]

    # Уровни пачкой
    levels_all: List[CardLevel] = (
        db.query(CardLevel)
        .filter(CardLevel.card_id.in_(card_ids))
        .order_by(CardLevel.card_id.asc(), CardLevel.level_index.asc())
        .all()
    )
    levels_by_card: dict[UUID, List[CardLevel]] = {}
    for lvl in levels_all:
        levels_by_card.setdefault(lvl.card_id, []).append(lvl)

    # activeLevel: читаем ТОЛЬКО активный прогресс (ничего не создаём)
    active_level_index_by_card: dict[UUID, int] = {}
    if mode in ("random", "ordered"):
        active_rows = (
            db.query(CardProgress.card_id, CardLevel.level_index)
            .join(CardLevel, CardLevel.id == CardProgress.card_level_id)
            .filter(
                CardProgress.user_id == user_id,
                CardProgress.card_id.in_(card_ids),
                CardProgress.is_active == True,
            )
            .all()
        )
        active_level_index_by_card = {card_id: lvl_index for card_id, lvl_index in active_rows}

    # Ответ в формате фронта (camelCase + нужные поля)
    out = []
    for c in cards:
        lvls = levels_by_card.get(c.id, [])
        if not lvls:
            continue

        out.append({
            "id": str(c.id),
            "deckId": str(c.deck_id),
            "title": c.title,
            "type": c.type,
            "levels": [{"levelIndex": l.level_index, "content": l.content} for l in lvls],
            "activeLevel": active_level_index_by_card.get(c.id, 0),
        })

    return {"cards": out}