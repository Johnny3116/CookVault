import uuid
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.units import Measure, merge

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"], dependencies=[Depends(require_auth)])


def _all_items(db: Session) -> list[models.ShoppingListItem]:
    return (
        db.query(models.ShoppingListItem)
        .order_by(models.ShoppingListItem.category, models.ShoppingListItem.name)
        .all()
    )


@router.get("", response_model=list[schemas.ShoppingListItemRead])
def list_items(db: Session = Depends(get_db)):
    return _all_items(db)


@router.post("/generate", response_model=list[schemas.ShoppingListItemRead])
def generate_from_recipes(payload: schemas.ShoppingListGenerateRequest, db: Session = Depends(get_db)):
    """Rebuild the generated half of the list from the given recipes.

    Duplicate ingredients are merged: two recipes wanting a cup of stock each
    become one "2 cup stock" line rather than two lines to reconcile in the
    shop. Amounts in compatible units are summed (see app/units.py); amounts
    that can't convert -- "2 cloves" against "1 tbsp" -- stay as separate
    lines rather than being silently added together.

    Calling this again replaces what the last call produced and leaves
    hand-added items alone, so generating twice gives the same list instead of
    doubling it.
    """
    recipes = db.query(models.Recipe).filter(models.Recipe.id.in_(payload.recipe_ids)).all()
    if len(recipes) != len(set(payload.recipe_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more recipes not found")

    db.query(models.ShoppingListItem).filter(
        models.ShoppingListItem.is_generated.is_(True)
    ).delete(synchronize_session=False)

    # Group by name and category: the same word in two categories (olive oil
    # as a pantry good in one recipe, a sauce in another) is two shopping
    # lines, and merging them would put it in an arbitrary column.
    grouped: OrderedDict[tuple[str, models.IngredientCategory], dict] = OrderedDict()
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            key = (ingredient.name.strip().lower(), ingredient.category)
            group = grouped.setdefault(
                key,
                {"name": ingredient.name.strip(), "measures": [], "recipe_ids": set()},
            )
            group["measures"].append(Measure(quantity=ingredient.quantity, unit=ingredient.unit))
            group["recipe_ids"].add(recipe.id)

    for (_, category), group in grouped.items():
        # Provenance only survives when a single recipe contributed; a merged
        # line has no one recipe to attribute it to.
        sole_recipe = next(iter(group["recipe_ids"])) if len(group["recipe_ids"]) == 1 else None
        for measure in merge(group["measures"]):
            db.add(
                models.ShoppingListItem(
                    recipe_id=sole_recipe,
                    name=group["name"],
                    quantity=measure.quantity,
                    unit=measure.unit,
                    category=category,
                    is_generated=True,
                )
            )

    db.commit()
    return _all_items(db)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_items(checked_only: bool = False, db: Session = Depends(get_db)):
    """Empty the list, or with checked_only just the items already ticked off."""
    query = db.query(models.ShoppingListItem)
    if checked_only:
        query = query.filter(models.ShoppingListItem.is_checked.is_(True))
    query.delete(synchronize_session=False)
    db.commit()


@router.post("", response_model=schemas.ShoppingListItemRead, status_code=status.HTTP_201_CREATED)
def add_item(payload: schemas.ShoppingListItemCreate, db: Session = Depends(get_db)):
    # Hand-added items survive regeneration.
    item = models.ShoppingListItem(**payload.model_dump(), is_generated=False)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=schemas.ShoppingListItemRead)
def update_item(item_id: uuid.UUID, payload: schemas.ShoppingListItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(models.ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    db.delete(item)
    db.commit()
