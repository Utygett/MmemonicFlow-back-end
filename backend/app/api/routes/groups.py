from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from uuid import UUID

from app.db.session import SessionLocal
from app.models.study_group import StudyGroup
from app.models.user_study_group import UserStudyGroup
from app.schemas.group import GroupCreate, GroupUpdate, GroupResponse
from app.schemas.cards import DeckWithCards, CardSummary
from app.models.user_study_group_deck import UserStudyGroupDeck
from app.models.deck import Deck
from app.models.card import Card
from app.auth.dependencies import get_current_user_id
from app.schemas.group import UserGroupResponse, GroupKind
from app.schemas.cards import DeckDetail
from app.models import CardProgress
from app.models import CardReviewHistory

router = APIRouter()

# -------------------------------
# Dependency для базы
# -------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------------------
# Создать группу
# -------------------------------
@router.post("/", response_model=GroupResponse)
def create_group(group_data: GroupCreate, user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    group = StudyGroup(
        owner_id=user_id,
        title=group_data.title,
        description=group_data.description,
        parent_id=group_data.parent_id
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Связь пользователя с группой
    user_group = UserStudyGroup(
        user_id=user_id,
        source_group_id=group.id,
        title_override=None,
        parent_id=None
    )
    db.add(user_group)
    db.commit()
    db.refresh(user_group)

    return GroupResponse(
        id=user_group.id,  #Временно возвращаю айди юзер группы так как поиск по айди основной группы ничего хорошего не выдает
        title=group.title,
        description=group.description,
        parent_id=group.parent_id
    )

# -------------------------------
# Получить список групп пользователя
# -------------------------------
@router.get("/", response_model=List[UserGroupResponse])
def list_groups(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserStudyGroup, StudyGroup)
        .outerjoin(StudyGroup, UserStudyGroup.source_group_id == StudyGroup.id)
        .filter(UserStudyGroup.user_id == user_id)
        .all()
    )

    out: List[UserGroupResponse] = []
    for ug, sg in rows:
        is_subscription = ug.source_group_id is not None

        kind = GroupKind.subscription if is_subscription else GroupKind.personal

        title = ug.title_override
        if not title:
            title = sg.title if sg else "Мои колоды"

        out.append(
            UserGroupResponse(
                user_group_id=ug.id,
                kind=kind,
                source_group_id=ug.source_group_id,

                title=title,
                description=(sg.description if sg else None),

                # parent_id — из UserStudyGroup (пользовательская иерархия)
                parent_id=ug.parent_id,
            )
        )

    return out

# -------------------------------
# Получить конкретную группу
# -------------------------------
@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: UUID, user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    group = (
        db.query(StudyGroup)
        .join(UserStudyGroup, UserStudyGroup.source_group_id == StudyGroup.id)
        .filter(StudyGroup.id == group_id)
        .filter(UserStudyGroup.user_id == user_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    return GroupResponse(
        id=group.id,
        title=group.title,
        description=group.description,
        parent_id=group.parent_id
    )

# -------------------------------
# Обновить группу
# -------------------------------
@router.patch("/{group_id}", response_model=GroupResponse)
def update_group(group_id: UUID, data: GroupUpdate, user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    group = db.query(StudyGroup).filter(StudyGroup.id == group_id, StudyGroup.owner_id == user_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if data.title is not None:
        group.title = data.title
    if data.description is not None:
        group.description = data.description

    db.commit()
    db.refresh(group)

    return GroupResponse(
        id=group.id,
        title=group.title,
        description=group.description,
        parent_id=group.parent_id
    )

# -------------------------------
# Удалить группу
# -------------------------------
@router.delete("/{user_group_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    user_group_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ug = (
        db.query(UserStudyGroup)
        .filter(UserStudyGroup.id == user_group_id,
                UserStudyGroup.user_id == user_id)
        .first()
    )
    if not ug:
        raise HTTPException(status_code=404, detail="Group not found")

    # Всегда чистим user-space links на колоды
    db.query(UserStudyGroupDeck).filter(
        UserStudyGroupDeck.user_group_id == ug.id
    ).delete(synchronize_session=False)

    # 1) Личная группа: source_group_id is NULL
    if ug.source_group_id is None:
        db.delete(ug)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # 2) Группа на базе StudyGroup
    sg = db.query(StudyGroup).filter(StudyGroup.id == ug.source_group_id).first()
    if not sg:
        raise HTTPException(status_code=404, detail="Source group not found")

    if sg.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system group")

    if sg.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot delete чужую группу")

    # Важно: удалить ВСЕ user-группы, которые ссылаются на эту StudyGroup (иначе FK violation)
    other_ugs = db.query(UserStudyGroup).filter(UserStudyGroup.source_group_id == sg.id).all()
    other_ug_ids = [x.id for x in other_ugs]

    if other_ug_ids:
        db.query(UserStudyGroupDeck).filter(
            UserStudyGroupDeck.user_group_id.in_(other_ug_ids)
        ).delete(synchronize_session=False)

    db.query(UserStudyGroup).filter(
        UserStudyGroup.source_group_id == sg.id
    ).delete(synchronize_session=False)

    db.delete(sg)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# -------------------------------
# Получить колоды группы вместе с карточками
# -------------------------------
@router.get("/{group_id}/decks", response_model=list[DeckWithCards])
def get_group_decks(group_id: UUID, user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # Проверяем, что пользователь связан с группой
    user_group = db.query(UserStudyGroup).filter(
        UserStudyGroup.user_id == user_id,
        UserStudyGroup.source_group_id == group_id
    ).first()
    if not user_group:
        raise HTTPException(status_code=404, detail="Group not found or access denied")

    # Получаем все колоды группы
    group_decks = db.query(UserStudyGroupDeck).filter(
        UserStudyGroupDeck.user_group_id == user_group.id
    ).all()

    result = []
    for ugd in group_decks:
        deck = db.query(Deck).filter(Deck.id == ugd.deck_id).first()
        if not deck:
            continue

        # Получаем карточки колоды
        cards = db.query(Card).filter(Card.deck_id == deck.id).all()
        cards_summary = [
            CardSummary(card_id=c.id, title=c.title, type=c.type)
            for c in cards
        ]

        result.append(
            DeckWithCards(
                deck=deck,
                cards=cards_summary
            )
        )

    return result


def assert_group_is_modifiable(ug: UserStudyGroup, user_id: UUID, db: Session) -> None:
    # personal group (source_group_id is NULL) — всегда модифицируемая
    if ug.source_group_id is None:
        return

    # иначе это "группа на базе StudyGroup"; модифицировать можно только владельцу StudyGroup
    sg = db.query(StudyGroup).filter(StudyGroup.id == ug.source_group_id).first()
    if not sg:
        raise HTTPException(404, "Source group not found")
    if sg.owner_id != user_id:
        raise HTTPException(403, "Cannot modify subscription group")

@router.put("/{user_group_id}/decks/{deck_id:uuid}", status_code=204)
def add_deck_to_user_group(
    user_group_id: UUID,
    deck_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ug = (
        db.query(UserStudyGroup)
        .filter(UserStudyGroup.id == user_group_id, UserStudyGroup.user_id == user_id)
        .first()
    )
    if not ug:
        raise HTTPException(404, "Group not found or access denied")

    assert_group_is_modifiable(ug, user_id, db)

    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(404, "Deck not found")

    if deck.owner_id != user_id and not deck.is_public:
        raise HTTPException(403, "Deck not accessible")

    existing = (
        db.query(UserStudyGroupDeck)
        .filter(UserStudyGroupDeck.user_group_id == ug.id, UserStudyGroupDeck.deck_id == deck_id)
        .first()
    )
    if existing:
        return

    max_order = (
        db.query(func.max(UserStudyGroupDeck.order_index))
        .filter(UserStudyGroupDeck.user_group_id == ug.id)
        .scalar()
    )
    next_order = (max_order + 1) if max_order is not None else 0

    db.add(UserStudyGroupDeck(user_group_id=ug.id, deck_id=deck_id, order_index=next_order))
    db.commit()

@router.delete("/{user_group_id}/decks/{deck_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def remove_deck_from_group(
    user_group_id: UUID,
    deck_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ug = (
        db.query(UserStudyGroup)
        .filter(UserStudyGroup.id == user_group_id, UserStudyGroup.user_id == user_id)
        .first()
    )
    if not ug:
        raise HTTPException(404, "Group not found or access denied")

    assert_group_is_modifiable(ug, user_id, db)

    deleted = (
        db.query(UserStudyGroupDeck)
        .filter(UserStudyGroupDeck.user_group_id == ug.id, UserStudyGroupDeck.deck_id == deck_id)
        .delete(synchronize_session=False)
    )
    db.commit()

    if deleted == 0:
        raise HTTPException(404, "Deck link not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{user_group_id}/decks/summary", response_model=List[DeckDetail])
def get_group_decks_summary(
    user_group_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ug = (
        db.query(UserStudyGroup)
        .filter(UserStudyGroup.id == user_group_id, UserStudyGroup.user_id == user_id)
        .first()
    )
    if not ug:
        raise HTTPException(404, "Group not found or access denied")

    links = (
        db.query(UserStudyGroupDeck)
        .filter(UserStudyGroupDeck.user_group_id == ug.id)
        .order_by(UserStudyGroupDeck.order_index.asc())
        .all()
    )
    deck_ids = [l.deck_id for l in links]
    if not deck_ids:
        return []

    decks = db.query(Deck).filter(Deck.id.in_(deck_ids)).all()
    deck_by_id = {d.id: d for d in decks}

    # --- агрегаты ---
    # cards_count
    cards_count_rows = (
        db.query(Card.deck_id, func.count(Card.id))
        .filter(Card.deck_id.in_(deck_ids))
        .group_by(Card.deck_id)
        .all()
    )
    cards_count_by_deck = {deck_id: cnt for deck_id, cnt in cards_count_rows}

    # completed_cards_count = distinct card_id in CardProgress
    completed_rows = (
        db.query(Card.deck_id, func.count(func.distinct(CardProgress.card_id)))
        .join(CardProgress, CardProgress.card_id == Card.id)
        .filter(Card.deck_id.in_(deck_ids), CardProgress.user_id == user_id)
        .group_by(Card.deck_id)
        .all()
    )
    completed_by_deck = {deck_id: cnt for deck_id, cnt in completed_rows}

    # count_repeat = count(CardReviewHistory) по колоде
    repeat_rows = (
        db.query(Card.deck_id, func.count(CardReviewHistory.id))
        .join(CardReviewHistory, CardReviewHistory.card_id == Card.id)
        .filter(
            Card.deck_id.in_(deck_ids),
            CardReviewHistory.user_id == user_id,
        )
        .group_by(Card.deck_id)
        .all()
    )
    repeat_by_deck = {deck_id: cnt for deck_id, cnt in repeat_rows}

    # count_for_repeat = distinct card_id where active and next_review <= now
    now = datetime.now(timezone.utc)
    due_rows = (
        db.query(Card.deck_id, func.count(func.distinct(CardProgress.card_id)))
        .join(CardProgress, CardProgress.card_id == Card.id)
        .filter(
            Card.deck_id.in_(deck_ids),
            CardProgress.user_id == user_id,
            CardProgress.is_active == True,
            CardProgress.next_review.isnot(None),
            CardProgress.next_review <= now,
        )
        .group_by(Card.deck_id)
        .all()
    )
    due_by_deck = {deck_id: cnt for deck_id, cnt in due_rows}

    # --- собрать ответ в порядке links ---
    out: List[DeckDetail] = []
    for did in deck_ids:
        d = deck_by_id.get(did)
        if not d:
            continue

        out.append(
            DeckDetail(
                id=d.id,  # заполнит deck_id через validation_alias
                title=d.title,
                description=d.description,
                color=d.color,
                owner_id=d.owner_id,
                is_public=d.is_public,

                cards_count=cards_count_by_deck.get(did, 0),
                completed_cards_count=completed_by_deck.get(did, 0),
                count_repeat=repeat_by_deck.get(did, 0),
                count_for_repeat=due_by_deck.get(did, 0),
            )
        )

    return out
