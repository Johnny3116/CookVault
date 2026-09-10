import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(
    prefix="/recipes/{recipe_id}/ingredients", tags=["ingredients"], dependencies=[Depends(require_auth)]
)


def _get_recipe_or_404(recipe_id: uuid.UUID, db: Session) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[schemas.IngredientRead])
def list_ingredients(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_recipe_or_404(recipe_id, db)
    return db.query(models.Ingredient).filter(models.Ingredient.recipe_id == recipe_id).all()


@router.post("", response_model=schemas.IngredientRead, status_code=status.HTTP_201_CREATED)
def add_ingredient(recipe_id: uuid.UUID, payload: schemas.IngredientCreate, db: Session = Depends(get_db)):
    _get_recipe_or_404(recipe_id, db)
    ingredient = models.Ingredient(recipe_id=recipe_id, **payload.model_dump())
    db.add(ingredient)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.patch("/{ingredient_id}", response_model=schemas.IngredientRead)
def update_ingredient(
    recipe_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    payload: schemas.IngredientBase,
    db: Session = Depends(get_db),
):
    ingredient = db.get(models.Ingredient, ingredient_id)
    if ingredient is None or ingredient.recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ingredient, field, value)
    db.commit()
    db.refresh(ingredient)
    return ingredient


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ingredient(recipe_id: uuid.UUID, ingredient_id: uuid.UUID, db: Session = Depends(get_db)):
    ingredient = db.get(models.Ingredient, ingredient_id)
    if ingredient is None or ingredient.recipe_id != recipe_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingredient not found")
    db.delete(ingredient)
    db.commit()
