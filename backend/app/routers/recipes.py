import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.services.scaling import effective_scale, scale_quantity
from app.units import tidy

router = APIRouter(prefix="/recipes", tags=["recipes"], dependencies=[Depends(require_auth)])


def _get_recipe_or_404(recipe_id: uuid.UUID, db: Session) -> models.Recipe:
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


@router.get("", response_model=list[schemas.RecipeSummary])
def list_recipes(
    favorite: bool | None = None,
    tag: str | None = None,
    max_total_time: int | None = None,
    cook_method: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
):
    """List recipes, narrowed by any combination of the filters.

    max_total_time is prep + cook in minutes. A recipe that records neither
    counts as 0 rather than being excluded -- an unknown time is not a long
    one, and dropping untimed recipes would hide most of a young library.
    """
    stmt = select(models.Recipe)
    if favorite is not None:
        stmt = stmt.where(models.Recipe.is_favorite == favorite)
    if tag is not None:
        stmt = stmt.where(models.Recipe.tags.contains([tag]))
    if cook_method is not None:
        stmt = stmt.where(models.Recipe.cook_methods.contains([cook_method]))
    if max_total_time is not None:
        total = func.coalesce(models.Recipe.prep_time, 0) + func.coalesce(models.Recipe.cook_time, 0)
        stmt = stmt.where(total <= max_total_time)
    if search is not None and search.strip():
        stmt = stmt.where(models.Recipe.title.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(models.Recipe.updated_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/facets", response_model=schemas.RecipeFacets)
def recipe_facets(db: Session = Depends(get_db)):
    """The tags and cook methods actually in use, so the UI can offer real
    choices instead of a free-text box the user has to guess at."""
    tags = db.execute(
        select(func.unnest(models.Recipe.tags).label("tag")).distinct().order_by("tag")
    ).scalars().all()
    methods = db.execute(
        select(func.unnest(models.Recipe.cook_methods).label("method")).distinct().order_by("method")
    ).scalars().all()
    return schemas.RecipeFacets(tags=list(tags), cook_methods=list(methods))


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
def get_recipe(
    recipe_id: uuid.UUID,
    servings: int | None = None,
    db: Session = Depends(get_db),
):
    """Read a recipe, optionally scaled to a target number of servings.

    Scaling is nondestructive -- the stored recipe is untouched and only the
    response is scaled. A recipe that doesn't record its own yield can't be
    scaled from, so it comes back unchanged with applied_scale left null
    rather than being scaled from a guessed baseline.
    """
    recipe = _get_recipe_or_404(recipe_id, db)
    if servings is None:
        return recipe

    if servings <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="servings must be greater than zero",
        )

    scale = effective_scale(recipe.servings, servings)
    detail = schemas.RecipeDetail.model_validate(recipe)
    if scale == 1:
        # Either the target matches, or the recipe has no yield to scale from.
        return detail

    detail.ingredients = [
        ingredient.model_copy(
            update={"quantity": _tidy_optional(scale_quantity(ingredient.quantity, scale))}
        )
        for ingredient in detail.ingredients
    ]
    detail.servings = servings
    detail.scaled_to_servings = servings
    detail.applied_scale = tidy(scale)
    return detail


def _tidy_optional(quantity):
    return None if quantity is None else tidy(quantity)


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
