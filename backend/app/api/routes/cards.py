# backend/app/api/routes/cards.py
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id
from app.db.session import SessionLocal
from app.models.card import Card
from app.models.card_level import CardLevel
from app.models.card_progress import CardProgress
from app.models.card_review_history import CardReviewHistory
from app.models.user_learning_settings import UserLearningSettings
from app.schemas.card_review import CardForReview, ReviewRequest, ReviewResponse
from app.schemas.cards import CardForReviewWithLevels, CardLevelContent
from app.services.review_service import ReviewService
from app.schemas.cards import CreateCardRequest
from app.schemas.cards import CreateCardResponse
from starlette import status
from app.models import Deck
from app.schemas.cards import CardSummary
from app.schemas.cards import ReplaceLevelsRequest

from app.schemas.cards import QaContentIn, McqContentIn

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _ensure_settings(db: Session, user_id: UUID) -> UserLearningSettings:
    settings = db.query(UserLearningSettings).filter_by(user_id=user_id).first()
    if settings:
        return settings
    settings = UserLearningSettings(user_id=user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _ensure_active_progress(db: Session, *, user_id: UUID, card: Card, settings: UserLearningSettings) -> CardProgress:
    # найти активный уровень
    progress = (
        db.query(CardProgress)
        .filter_by(user_id=user_id, card_id=card.id, is_active=True)
        .first()
    )
    if progress:
        return progress

    # если нет — создаём уровень 0
    lvl0 = db.query(CardLevel).filter_by(card_id=card.id, level_index=0).first()
    if not lvl0:
        raise HTTPException(status_code=500, detail="Card has no level 0")

    now = datetime.now(timezone.utc)
    progress = CardProgress(
        user_id=user_id,
        card_id=card.id,
        card_level_id=lvl0.id,
        is_active=True,
        stability=settings.initial_stability,
        difficulty=settings.initial_difficulty,
        last_reviewed=None,
        next_review=now,
    )
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return progress


@router.post("/", response_model=CreateCardResponse, status_code=status.HTTP_201_CREATED)
def create_card(
    payload: CreateCardRequest,
    userid: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # 1) deck exists
    deck = db.query(Deck).filter(Deck.id == payload.deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    # 2) owner-only
    if deck.owner_id != userid:
        raise HTTPException(status_code=403, detail="Deck not accessible")  # owner-only

    # 3) validate minimal invariants
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")
    if not payload.levels:
        raise HTTPException(status_code=422, detail="At least 1 level is required")

    # 4) create card (ORM uses deckid/maxlevel) [file:151]
    card = Card(
        deck_id=payload.deck_id,
        title=title,
        type=payload.type,
        max_level=len(payload.levels) - 1,
        settings=None,
    )
    db.add(card)
    db.flush()  # получаем card.id до insert levels

    # 5) create levels (ORM uses cardid/levelindex/content)
    levels_to_add = []

    for i, lvl in enumerate(payload.levels):
        q = (lvl.question or "").strip()
        if not q:
            raise HTTPException(status_code=422, detail=f"Level {i + 1}: question is required")

        if payload.type == "flashcard":
            a = (lvl.answer or "").strip()
            if not a:
                raise HTTPException(status_code=422, detail=f"Level {i + 1}: answer is required for flashcard")

            content = {"question": q, "answer": a}

        elif payload.type == "multiple_choice":
            options = lvl.options or []
            if len(options) < 2:
                raise HTTPException(status_code=422, detail=f"Level {i + 1}: at least 2 options required")

            # trim option texts
            options_norm = [{"id": o.id, "text": (o.text or "").strip()} for o in options]
            non_empty = [o for o in options_norm if o["text"]]
            if len(non_empty) < 2:
                raise HTTPException(status_code=422, detail=f"Level {i + 1}: at least 2 non-empty options required")

            correct_id = (lvl.correctOptionId or "").strip()
            if not correct_id:
                raise HTTPException(status_code=422, detail=f"Level {i + 1}: correctOptionId is required")

            correct = next((o for o in options_norm if o["id"] == correct_id), None)
            if not correct or not correct["text"]:
                raise HTTPException(status_code=422,
                                    detail=f"Level {i + 1}: correctOptionId must point to a non-empty option")

            timer = lvl.timerSec
            if timer is not None and (timer < 1 or timer > 3600):
                raise HTTPException(status_code=422, detail=f"Level {i + 1}: timerSec must be 1..3600")

            content = {
                "question": q,
                "options": options_norm,
                "correctOptionId": correct_id,
                "explanation": (lvl.explanation or "").strip() or None,
                "timerSec": timer,
            }

        else:
            raise HTTPException(status_code=422, detail=f"Unsupported card type: {payload.type}")

        levels_to_add.append(
            CardLevel(
                card_id=card.id,
                level_index=i,
                content=content,
            )
        )

    db.add_all(levels_to_add)

    db.commit()

    return CreateCardResponse(card_id=card.id, deck_id=payload.deck_id)

@router.get("/review", response_model=list[CardForReview])
def get_cards_for_review(
    user_id: UUID = Depends(get_current_user_id),
    limit: int = 20,
    db: Session = Depends(get_db),
):
    user_uuid = user_id
    now = datetime.now(timezone.utc)

    progress_list = (
        db.query(CardProgress)
        .filter(CardProgress.user_id == user_uuid)
        .filter(CardProgress.is_active == True)
        .filter(CardProgress.next_review <= now)
        .order_by(CardProgress.next_review.asc())
        .limit(limit)
        .all()
    )

    result: list[CardForReview] = []
    for progress in progress_list:
        card = db.get(Card, progress.card_id)
        level = db.get(CardLevel, progress.card_level_id)
        result.append(
            CardForReview(
                card_id=card.id,
                deck_id=card.deck_id,
                title=card.title,
                type=card.type,
                card_level_id=level.id,
                level_index=level.level_index,
                content=level.content,
                stability=progress.stability,
                difficulty=progress.difficulty,
                next_review=progress.next_review,
            )
        )
    return result

@router.post("/{card_id}/review", response_model=ReviewResponse)
async def review_card(
    card_id: UUID,
    payload: ReviewRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_uuid = user_id

    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    settings = _ensure_settings(db, user_uuid)
    progress = _ensure_active_progress(db, user_id=user_uuid, card=card, settings=settings)

    updated = ReviewService.review(
        progress=progress,
        rating=payload.rating.value,
        settings=settings,
        rated_at=payload.rated_at,
    )

    progress.stability = updated.stability
    progress.difficulty = updated.difficulty
    progress.last_reviewed = payload.rated_at
    progress.next_review = updated.next_review
    db.add(progress)

    history_entry = CardReviewHistory(
        user_id=user_uuid,
        card_id=card.id,
        card_level_id=progress.card_level_id,
        rating=payload.rating,
        interval_minutes=int((progress.next_review - payload.rated_at).total_seconds() // 60),
        show_at=payload.shown_at,
        reveal_at=payload.revealed_at or payload.rated_at,
        reviewed_at=payload.rated_at,
    )
    db.add(history_entry)

    db.commit()
    db.refresh(progress)

    level = db.get(CardLevel, progress.card_level_id)
    return ReviewResponse(
        card_id=card.id,
        card_level_id=level.id,
        level_index=level.level_index,
        stability=progress.stability,
        difficulty=progress.difficulty,
        next_review=progress.next_review,
    )


@router.post("/{card_id}/level_up")
def level_up(
    card_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_uuid = user_id
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(404, "Card not found")

    settings = _ensure_settings(db, user_uuid)
    current = (
        db.query(CardProgress)
        .filter_by(user_id=user_uuid, card_id=card_id, is_active=True)
        .first()
    )
    if not current:
        current = _ensure_active_progress(db, user_id=user_uuid, card=card, settings=settings)

    current_level = db.get(CardLevel, current.card_level_id)
    next_level_index = current_level.level_index + 1

    next_level = (
        db.query(CardLevel)
        .filter_by(card_id=card_id, level_index=next_level_index)
        .first()
    )
    if not next_level:
        raise HTTPException(400, "No next level")

    # deactivate current
    current.is_active = False
    db.add(current)
    db.flush()

    # activate/create next progress
    next_progress = (
        db.query(CardProgress)
        .filter_by(user_id=user_uuid, card_level_id=next_level.id)
        .first()
    )

    now = datetime.now(timezone.utc)
    if not next_progress:
        next_progress = CardProgress(
            user_id=user_uuid,
            card_id=card_id,
            card_level_id=next_level.id,
            is_active=True,
            stability=current.stability * settings.promote_stability_multiplier,
            difficulty=current.difficulty + settings.promote_difficulty_delta,
            last_reviewed=now,
            next_review=now,  # можно сделать now + 10 минут, если хочешь "контрольный" повтор
        )
        db.add(next_progress)
    else:
        next_progress.is_active = True
        db.add(next_progress)

    db.commit()
    return {"active_level_index": next_level.level_index, "active_card_level_id": str(next_level.id)}


@router.post("/{card_id}/level_down")
def level_down(
    card_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user_uuid = user_id
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(404, "Card not found")

    current = (
        db.query(CardProgress)
        .filter_by(user_id=user_uuid, card_id=card_id, is_active=True)
        .first()
    )
    if not current:
        raise HTTPException(404, "Active progress not found")

    current_card_level = db.get(CardLevel, current.card_level_id)
    prev_level_index = current_card_level.level_index - 1
    if prev_level_index < 0:
        raise HTTPException(400, "Already at level 0")

    prev_level = (
        db.query(CardLevel)
        .filter_by(card_id=card_id, level_index=prev_level_index)
        .first()
    )
    if not prev_level:
        raise HTTPException(400, "No previous level")

    # deactivate current
    current.is_active = False
    db.add(current)
    db.flush()

    prev_progress = (
        db.query(CardProgress)
        .filter_by(user_id=user_uuid, card_level_id=prev_level.id)
        .first()
    )
    if not prev_progress:
        # если раньше не учил этот уровень — создаём
        settings = _ensure_settings(db, user_uuid)
        now = datetime.now(timezone.utc)
        prev_progress = CardProgress(
            user_id=user_uuid,
            card_id=card_id,
            card_level_id=prev_level.id,
            is_active=True,
            stability=settings.initial_stability,
            difficulty=settings.initial_difficulty,
            last_reviewed=now,
            next_review=now,
        )
        db.add(prev_progress)
    else:
        prev_progress.is_active = True
        db.add(prev_progress)

    db.commit()
    return {"active_level_index": prev_level.level_index, "active_card_level_id": str(prev_level.id)}


@router.get("/review_with_levels", response_model=list[CardForReviewWithLevels])
def get_cards_for_review_with_levels(
    user_id: UUID = Depends(get_current_user_id),
    limit: int = 20,
    db: Session = Depends(get_db),
):
    user_uuid = user_id
    now = datetime.now(timezone.utc)

    progress_list = (
        db.query(CardProgress)
        .filter(CardProgress.user_id == user_uuid)
        .filter(CardProgress.is_active == True)
        .filter(CardProgress.next_review <= now)
        .order_by(CardProgress.next_review.asc())
        .limit(limit)
        .all()
    )

    card_ids = [p.card_id for p in progress_list]
    levels_all = (
        db.query(CardLevel)
        .filter(CardLevel.card_id.in_(card_ids))
        .order_by(CardLevel.card_id.asc(), CardLevel.level_index.asc())
        .all()
    )
    levels_by_card: dict[UUID, list[CardLevel]] = {}
    for lvl in levels_all:
        levels_by_card.setdefault(lvl.card_id, []).append(lvl)

    result: list[CardForReviewWithLevels] = []
    for progress in progress_list:
        card = db.get(Card, progress.card_id)
        level = db.get(CardLevel, progress.card_level_id)

        result.append(
            CardForReviewWithLevels(
                card_id=card.id,
                deck_id=card.deck_id,
                title=card.title,
                type=card.type,
                card_level_id=level.id,
                level_index=level.level_index,
                content=level.content,
                stability=progress.stability,
                difficulty=progress.difficulty,
                next_review=progress.next_review,
                levels=[
                    CardLevelContent(level_index=l.level_index, content=l.content)
                    for l in levels_by_card.get(card.id, [])
                ],
            )
        )
    return result


@router.put("/{card_id}/levels", response_model=CardSummary)
def update_card_levels(
    card_id: UUID,
    payload: ReplaceLevelsRequest,
    userid: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    deck = db.get(Deck, card.deck_id)
    if not deck or deck.owner_id != userid:
        raise HTTPException(status_code=403, detail="Deck not accessible")

    if not payload.levels:
        raise HTTPException(status_code=422, detail="At least 1 level is required")

    if len(payload.levels) > 10:
        raise HTTPException(status_code=422, detail="Too many levels (max 10)")

    # Приведём к порядку по level_index (раз у тебя он есть в payload)
    incoming = sorted(payload.levels, key=lambda x: x.level_index)

    # (опционально) проверим что индексы подряд 0..n-1, иначе можно словить странные дыры
    for expected_idx, lvl in enumerate(incoming):
        if lvl.level_index != expected_idx:
            raise HTTPException(status_code=422, detail="level_index must be sequential starting from 0")

    # Полная замена: удаляем старые и пишем новые (так поддерживается изменение количества уровней)
    db.query(CardLevel).filter(CardLevel.card_id == card_id).delete(synchronize_session=False)
    db.flush()

    new_rows: List[CardLevel] = []

    for idx, lvl in enumerate(incoming):
        c = lvl.content

        if isinstance(c, QaContentIn):
            q = (c.question or "").strip()
            a = (c.answer or "").strip()
            if not q or not a:
                raise HTTPException(status_code=422, detail="QA level question/answer must be non-empty")

            content: Dict[str, Any] = {"question": q, "answer": a}

        elif isinstance(c, McqContentIn):
            q = (c.question or "").strip()
            if not q:
                raise HTTPException(status_code=422, detail="MCQ question must be non-empty")

            options = [{"id": str(o.id), "text": (o.text or "").strip()} for o in (c.options or [])]
            options = [o for o in options if o["text"]]

            if len(options) < 2:
                raise HTTPException(status_code=422, detail="MCQ must have at least 2 non-empty options")

            ids = [o["id"] for o in options]
            if len(set(ids)) != len(ids):
                raise HTTPException(status_code=422, detail="MCQ option ids must be unique")

            correct_id = str(c.correctOptionId)
            if correct_id not in set(ids):
                raise HTTPException(status_code=422, detail="MCQ correctOptionId must match one of options")

            content = {
                "question": q,
                "options": options,
                "correctOptionId": correct_id,
                "explanation": (c.explanation or "").strip(),
                "timerSec": int(c.timerSec or 0),
            }

        else:
            raise HTTPException(status_code=422, detail="Unsupported level content")

        row = CardLevel(
            card_id=card_id,
            level_index=idx,
            content=content,
        )
        new_rows.append(row)

    db.add_all(new_rows)
    db.commit()

    return CardSummary(
        card_id=card.id,
        title=card.title,
        type=card.type,
        levels=[CardLevelContent(level_index=r.level_index, content=r.content) for r in new_rows],
    )

@router.delete("/{card_id}/progress", status_code=204)
def delete_card_progress(
    card_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    (
        db.query(CardProgress)
        .filter(CardProgress.user_id == user_id, CardProgress.card_id == card_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return Response(status_code=204)

@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: UUID, user_id: UUID = Depends(get_current_user_id), db: Session = Depends(get_db)):
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    deck = db.get(Deck, card.deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    if deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="You are not the owner of this card")

    db.delete(card)
    db.commit()


@router.patch("/{card_id}", response_model=CardSummary)
def update_card(
        card_id: UUID,
        title: Optional[str] = None,  # будет приходить как query ?title=...
        user_id: UUID = Depends(get_current_user_id),
        db: Session = Depends(get_db),
):
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    deck = db.get(Deck, card.deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    if deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Card not accessible")

    if title is not None:
        t = title.strip()
        if not t:
            raise HTTPException(status_code=422, detail="Title is required")
        card.title = t

    db.commit()
    db.refresh(card)

    levels = (
        db.query(CardLevel)
        .filter(CardLevel.card_id == card.id)
        .order_by(CardLevel.level_index.asc())
        .all()
    )

    return CardSummary(
        card_id=card.id,
        title=card.title,
        type=card.type,
        levels=[CardLevelContent(level_index=l.level_index, content=l.content) for l in levels],
    )