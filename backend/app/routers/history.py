"""The cooking log: what was actually made, and when.

Logging is separate from planning on purpose. A meal plan is an intention and
is edited freely right up until the day; the log is a record of something that
happened, and nothing should rewrite it just because the plan changed. They
answer different questions, so they are different tables.
"""

import uuid
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(tags=["history"], dependencies=[Depends(require_auth)])


def _get_entry_or_404(entry_id: uuid.UUID, db: Session) -> models.CookLog:
    entry = db.get(models.CookLog, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    return entry


@router.post(
    "/recipes/{recipe_id}/cooked",
    response_model=schemas.CookLogRead,
    status_code=status.HTTP_201_CREATED,
)
def log_cooked(
    recipe_id: uuid.UUID, payload: schemas.CookLogCreate, db: Session = Depends(get_db)
):
    """Record that this was cooked.

    The same recipe can be logged twice on one day without complaint -- people
    do cook the same thing for lunch and dinner, and refusing that would make
    the log lie to keep a constraint happy.
    """
    if db.get(models.Recipe, recipe_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")

    data = payload.model_dump()
    entry = models.CookLog(
        recipe_id=recipe_id,
        # Logging a meal you have just eaten is the common case.
        cooked_on=data.pop("cooked_on") or date_type.today(),
        **data,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/recipes/{recipe_id}/history", response_model=list[schemas.CookLogRead])
def recipe_history(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    if db.get(models.Recipe, recipe_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    stmt = (
        select(models.CookLog)
        .where(models.CookLog.recipe_id == recipe_id)
        .order_by(models.CookLog.cooked_on.desc(), models.CookLog.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@router.get("/history", response_model=list[schemas.CookLogEntry])
def recent_history(
    limit: int = Query(default=50, ge=1, le=500),
    since: date_type | None = None,
    db: Session = Depends(get_db),
):
    """What has been cooked lately, newest first, with titles attached."""
    stmt = (
        select(models.CookLog, models.Recipe.title)
        .join(models.Recipe, models.Recipe.id == models.CookLog.recipe_id)
        .order_by(models.CookLog.cooked_on.desc(), models.CookLog.created_at.desc())
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(models.CookLog.cooked_on >= since)

    return [
        schemas.CookLogEntry(
            **schemas.CookLogRead.model_validate(entry).model_dump(), recipe_title=title
        )
        for entry, title in db.execute(stmt).all()
    ]


@router.patch("/history/{entry_id}", response_model=schemas.CookLogRead)
def update_entry(
    entry_id: uuid.UUID, payload: schemas.CookLogUpdate, db: Session = Depends(get_db)
):
    entry = _get_entry_or_404(entry_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(_get_entry_or_404(entry_id, db))
    db.commit()
