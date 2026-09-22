"""The pantry: a list of things you keep in.

There is no quantity here and that is the design, not an omission. The moment
this tracks how much is left, someone has to keep that accurate, and the only
person available is the one who wanted to cook dinner.

What it is for is one flag on the shopping list: you probably already have
this. It never removes a line -- see `shopping_list.py`.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/pantry", tags=["pantry"], dependencies=[Depends(require_auth)])


def load_names(db: Session) -> list[str]:
    return list(db.execute(select(models.PantryItem.name)).scalars().all())


def _get_or_404(item_id: uuid.UUID, db: Session) -> models.PantryItem:
    item = db.get(models.PantryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pantry item not found")
    return item


@router.get("", response_model=list[schemas.PantryItemRead])
def list_items(db: Session = Depends(get_db)):
    return db.execute(select(models.PantryItem).order_by(models.PantryItem.name)).scalars().all()


@router.post("", response_model=schemas.PantryItemRead, status_code=status.HTTP_201_CREATED)
def add_item(payload: schemas.PantryItemCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A pantry item needs a name.")

    item = models.PantryItem(name=name, note=payload.note)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"{name!r} is already in the pantry."
        ) from None
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=schemas.PantryItemRead)
def update_item(item_id: uuid.UUID, payload: schemas.PantryItemUpdate, db: Session = Depends(get_db)):
    item = _get_or_404(item_id, db)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="A pantry item needs a name."
            )
        item.name = name
    if "note" in data:
        item.note = data["note"]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That is already in the pantry."
        ) from None
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(_get_or_404(item_id, db))
    db.commit()
