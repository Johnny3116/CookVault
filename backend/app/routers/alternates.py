import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(
    prefix="/recipes/{recipe_id}/alternates", tags=["alternates"], dependencies=[Depends(require_auth)]
)


def _get_recipe_or_404(recipe_id: uuid.UUID, db: Session) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[schemas.AlternateRead])
def list_alternates(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_recipe_or_404(recipe_id, db)
    return db.query(models.Alternate).filter(models.Alternate.recipe_id == recipe_id).all()


@router.post("", response_model=schemas.AlternateRead, status_code=status.HTTP_201_CREATED)
def add_alternate(recipe_id: uuid.UUID, payload: schemas.AlternateCreate, db: Session = Depends(get_db)):
    _get_recipe_or_404(recipe_id, db)
    alternate = models.Alternate(recipe_id=recipe_id, **payload.model_dump())
    db.add(alternate)
    db.commit()
    db.refresh(alternate)
    return alternate


@router.patch("/{alternate_id}", response_model=schemas.AlternateRead)
def update_alternate(
    recipe_id: uuid.UUID,
    alternate_id: uuid.UUID,
    payload: schemas.AlternateUpdate,
    db: Session = Depends(get_db),
):
    alternate = db.get(models.Alternate, alternate_id)
    if alternate is None or alternate.recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alternate not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alternate, field, value)
    db.commit()
    db.refresh(alternate)
    return alternate


@router.delete("/{alternate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alternate(recipe_id: uuid.UUID, alternate_id: uuid.UUID, db: Session = Depends(get_db)):
    alternate = db.get(models.Alternate, alternate_id)
    if alternate is None or alternate.recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alternate not found")
    db.delete(alternate)
    db.commit()
