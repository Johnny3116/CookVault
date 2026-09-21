import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/recipes/{recipe_id}/steps", tags=["steps"], dependencies=[Depends(require_auth)])


def _get_recipe_or_404(recipe_id: uuid.UUID, db: Session) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[schemas.StepRead])
def list_steps(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_recipe_or_404(recipe_id, db)
    return (
        db.query(models.Step)
        .filter(models.Step.recipe_id == recipe_id)
        .order_by(models.Step.order)
        .all()
    )


@router.post("", response_model=schemas.StepRead, status_code=status.HTTP_201_CREATED)
def add_step(recipe_id: uuid.UUID, payload: schemas.StepCreate, db: Session = Depends(get_db)):
    _get_recipe_or_404(recipe_id, db)
    step = models.Step(recipe_id=recipe_id, **payload.model_dump())
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.patch("/{step_id}", response_model=schemas.StepRead)
def update_step(recipe_id: uuid.UUID, step_id: uuid.UUID, payload: schemas.StepUpdate, db: Session = Depends(get_db)):
    step = db.get(models.Step, step_id)
    if step is None or step.recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(step, field, value)
    db.commit()
    db.refresh(step)
    return step


@router.delete("/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(recipe_id: uuid.UUID, step_id: uuid.UUID, db: Session = Depends(get_db)):
    step = db.get(models.Step, step_id)
    if step is None or step.recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    db.delete(step)
    db.commit()
