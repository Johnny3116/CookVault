import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[schemas.MealPlanEntryRead])
def list_entries(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    query = db.query(models.MealPlanEntry)
    if start is not None:
        query = query.filter(models.MealPlanEntry.date >= start)
    if end is not None:
        query = query.filter(models.MealPlanEntry.date <= end)
    return query.order_by(models.MealPlanEntry.date).all()


@router.post("", response_model=schemas.MealPlanEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: schemas.MealPlanEntryCreate, db: Session = Depends(get_db)):
    if payload.mode == models.MealPlanMode.auto:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Auto-fill meal planning is a Phase 2 feature and isn't built yet.",
        )
    entry = models.MealPlanEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}", response_model=schemas.MealPlanEntryRead)
def update_entry(
    entry_id: uuid.UUID, payload: schemas.MealPlanEntryUpdate, db: Session = Depends(get_db)
):
    """Move an entry, or change the servings or meal slot planned for it."""
    entry = db.get(models.MealPlanEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.get(models.MealPlanEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    db.delete(entry)
    db.commit()


@router.post("/auto-fill", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def auto_fill(week_start: date):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Auto-fill meal planning is a Phase 2 feature -- needs the Agent Zero "
            "integration for variety/budget optimization. Not implemented yet."
        ),
    )
