import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(require_auth)])


def _get_recipe_or_404(recipe_id: uuid.UUID, db: Session) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[schemas.RecipeSummary])
def list_recipes(
    favorite: bool | None = None,
    cuisine: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(models.Recipe)
    if favorite is not None:
        stmt = stmt.where(models.Recipe.is_favorite == favorite)
    if cuisine is not None:
        stmt = stmt.where(models.Recipe.tags.contains([cuisine]))
    stmt = stmt.order_by(models.Recipe.updated_at.desc())
    return db.execute(stmt).scalars().all()


def _apply_children(recipe: models.Recipe, payload: schemas.RecipeCreate) -> None:
    """Set the recipe's children from the payload, preserving submitted order."""
    recipe.ingredients = [
        models.Ingredient(position=index, **ingredient.model_dump())
        for index, ingredient in enumerate(payload.ingredients)
    ]
    recipe.steps = [models.Step(**step.model_dump()) for step in payload.steps]
    recipe.alternates = [models.Alternate(**alt.model_dump()) for alt in payload.alternates]


@router.post("", response_model=schemas.RecipeDetail, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: schemas.RecipeCreate, db: Session = Depends(get_db)):
    data = payload.model_dump(exclude={"ingredients", "steps", "alternates"})
    recipe = models.Recipe(**data)
    _apply_children(recipe, payload)
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.get("/{recipe_id}", response_model=schemas.RecipeDetail)
def get_recipe(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_recipe_or_404(recipe_id, db)


@router.patch("/{recipe_id}", response_model=schemas.RecipeDetail)
def update_recipe(recipe_id: uuid.UUID, payload: schemas.RecipeUpdate, db: Session = Depends(get_db)):
    recipe = _get_recipe_or_404(recipe_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(recipe, field, value)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.put("/{recipe_id}", response_model=schemas.RecipeDetail)
def replace_recipe(recipe_id: uuid.UUID, payload: schemas.RecipeReplace, db: Session = Depends(get_db)):
    """Replace a recipe and all its children in one call.

    The edit form submits the whole recipe, so replacing wholesale avoids making
    the client diff children against per-child endpoints.
    """
    recipe = _get_recipe_or_404(recipe_id, db)
    for field, value in payload.model_dump(exclude={"ingredients", "steps", "alternates"}).items():
        setattr(recipe, field, value)
    _apply_children(recipe, payload)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    recipe = _get_recipe_or_404(recipe_id, db)
    db.delete(recipe)
    db.commit()
