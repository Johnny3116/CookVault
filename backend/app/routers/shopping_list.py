import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.routers.aisles import load_rules
from app.routers.pantry import load_names
from app.services.aisles import aisle_sort_key, longest_match, resolve_aisle
from app.services.shopping_list import PlannedRecipe, build_items

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"], dependencies=[Depends(require_auth)])


def _read(
    item: models.ShoppingListItem, rules, pantry: list[str]
) -> schemas.ShoppingListItemRead:
    """One row plus the aisle the rules put it in and whether it's a staple.

    Both are resolved per response rather than stored: fixing a rule, or
    putting something in the pantry, then applies to every line that relied on
    it instead of only the ones added afterwards.
    """
    read = schemas.ShoppingListItemRead.model_validate(item)
    read.aisle = resolve_aisle(item.name, item.aisle_override, rules)
    # A hint, never a subtraction. Dropping the line would silently under-buy,
    # which is worse than buying a second jar of cumin.
    read.in_pantry = longest_match(item.name, pantry) is not None
    return read


def _all_items(db: Session) -> list[schemas.ShoppingListItemRead]:
    """The list in shop order: aisle by aisle, alphabetical within each.

    Sorted here rather than in SQL because the aisle isn't a column -- it comes
    from the rules, which are rows of their own.
    """
    rules = load_rules(db)
    pantry = load_names(db)
    items = [
        _read(item, rules, pantry)
        for item in db.query(models.ShoppingListItem).order_by(models.ShoppingListItem.name).all()
    ]
    return sorted(items, key=lambda item: (aisle_sort_key(item.aisle), item.name.lower()))


@router.get("", response_model=list[schemas.ShoppingListItemRead])
def list_items(db: Session = Depends(get_db)):
    return _all_items(db)


@router.post("/generate", response_model=list[schemas.ShoppingListItemRead])
def generate(payload: schemas.ShoppingListGenerateRequest, db: Session = Depends(get_db)):
    """Rebuild the generated half of the list.

    Sources combine: `start`/`end` pull the meal plan for that span and buy the
    servings actually planned for each day, while bare `recipe_ids` are bought
    as written. Duplicate ingredients are merged across everything -- two
    recipes wanting a cup of stock become one "2 cup" line rather than two
    lines to reconcile in the shop. Amounts that can't convert stay separate
    rather than being silently added together.

    Calling this again replaces what the last call produced and leaves
    hand-added items alone, so generating twice gives the same list.
    """
    if (payload.start is None) != (payload.end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start and end must be given together",
        )
    if payload.start and payload.end and payload.start > payload.end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start must not be after end",
        )

    planned: list[PlannedRecipe] = []

    if payload.start and payload.end:
        entries = (
            db.query(models.MealPlanEntry)
            .filter(models.MealPlanEntry.date >= payload.start)
            .filter(models.MealPlanEntry.date <= payload.end)
            .order_by(models.MealPlanEntry.date)
            .all()
        )
        planned.extend(
            PlannedRecipe(recipe=entry.recipe, target_servings=entry.servings) for entry in entries
        )

    if payload.recipe_ids:
        recipes = db.query(models.Recipe).filter(models.Recipe.id.in_(payload.recipe_ids)).all()
        if len(recipes) != len(set(payload.recipe_ids)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="One or more recipes not found"
            )
        by_id = {recipe.id: recipe for recipe in recipes}
        # Preserve the caller's order rather than the database's.
        planned.extend(PlannedRecipe(recipe=by_id[rid]) for rid in payload.recipe_ids)

    db.query(models.ShoppingListItem).filter(
        models.ShoppingListItem.is_generated.is_(True)
    ).delete(synchronize_session=False)

    for item in build_items(planned):
        db.add(
            models.ShoppingListItem(
                recipe_id=item.recipe_id,
                name=item.name,
                quantity=item.quantity,
                unit=item.unit,
                category=item.category,
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
    return _read(item, load_rules(db), load_names(db))


@router.patch("/{item_id}", response_model=schemas.ShoppingListItemRead)
def update_item(item_id: uuid.UUID, payload: schemas.ShoppingListItemUpdate, db: Session = Depends(get_db)):
    item = db.get(models.ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _read(item, load_rules(db), load_names(db))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: uuid.UUID, db: Session = Depends(get_db)):
    item = db.get(models.ShoppingListItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    db.delete(item)
    db.commit()
