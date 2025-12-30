# backend/app/api/routes/cards.py
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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

    # 5) create levels (ORM uses cardid/levelindex/content) [file:151]
    db.add_all([
        CardLevel(
            card_id=card.id,
            level_index=i,
            content={"question": lvl.question, "answer": lvl.answer},
        )
        for i, lvl in enumerate(payload.levels)
    ])

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
def review_card(
    card_id: UUID,
    request: ReviewRequest,
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
        rating=request.rating.value,
        settings=settings,
    )

    # применяем результат к ORM progress
    progress.stability = updated.stability
    progress.difficulty = updated.difficulty
    progress.last_reviewed = updated.last_reviewed
    progress.next_review = updated.next_review
    db.add(progress)

    history_entry = CardReviewHistory(
        user_id=user_uuid,
        card_id=card.id,
        card_level_id=progress.card_level_id,
        rating=request.rating,
        interval_minutes=int((progress.next_review - progress.last_reviewed).total_seconds() // 60),
        reviewed_at=progress.last_reviewed,
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

    existing = (
        db.query(CardLevel)
        .filter(CardLevel.card_id == card_id)
        .order_by(CardLevel.level_index.asc())
        .all()
    )

    if not payload.levels:
        raise HTTPException(status_code=422, detail="At least 1 level is required")

    # Вариант 1 (самый безопасный): строго одинаковое число уровней
    if len(payload.levels) != len(existing):
        raise HTTPException(status_code=409, detail="Levels count mismatch")

    for i, lvl in enumerate(payload.levels):
        q = lvl.question.strip()
        a = lvl.answer.strip()
        if not q or not a:
            raise HTTPException(status_code=422, detail="Level question/answer must be non-empty")

        existing[i].content = {"question": q, "answer": a}

    db.commit()

    return CardSummary(
        card_id=card.id,
        title=card.title,
        type=card.type,
        levels=[
            CardLevelContent(level_index=l.level_index, content=l.content)
            for l in existing
        ],
    )