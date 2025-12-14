from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.db.session import SessionLocal
from app.models.study_group import StudyGroup
from app.models.user_study_group import UserStudyGroup
from app.schemas.group import GroupCreate, GroupUpdate, GroupResponse

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
def create_group(user_id: str, group_data: GroupCreate, db: Session = Depends(get_db)):
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
        id=group.id,
        title=group.title,
        description=group.description,
        parent_id=group.parent_id
    )

# -------------------------------
# Получить список групп пользователя
# -------------------------------
@router.get("/", response_model=List[GroupResponse])
def list_groups(user_id: str, db: Session = Depends(get_db)):
    groups = (
        db.query(StudyGroup)
        .join(UserStudyGroup, UserStudyGroup.source_group_id == StudyGroup.id)
        .filter(UserStudyGroup.user_id == user_id)
        .all()
    )
    return [
        GroupResponse(
            id=g.id,
            title=g.title,
            description=g.description,
            parent_id=g.parent_id
        )
        for g in groups
    ]

# -------------------------------
# Получить конкретную группу
# -------------------------------
@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: str, user_id: str, db: Session = Depends(get_db)):
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
def update_group(group_id: str, user_id: str, data: GroupUpdate, db: Session = Depends(get_db)):
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
@router.delete("/{group_id}")
def delete_group(group_id: str, user_id: str, db: Session = Depends(get_db)):
    group = db.query(StudyGroup).filter(StudyGroup.id == group_id, StudyGroup.owner_id == user_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Сначала удаляем связь пользователя
    db.query(UserStudyGroup).filter(UserStudyGroup.source_group_id == group.id, UserStudyGroup.user_id == user_id).delete()
    db.delete(group)
    db.commit()

    return {"status": "deleted"}
