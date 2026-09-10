import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/shopping-list", tags=["shopping-list"], dependencies=[Depends(require_auth)])


@router.get("", response_model=list[schemas.ShoppingListItemRead])
def list_items(db: Session = Depends(get_db)):
    return db.query(models.ShoppingListItem).order_by(models.ShoppingListItem.category).all()


@router.post("/generate", response_model=list[schemas.ShoppingListItemRead])
def generate_from_recipes(payload: schemas.ShoppingListGenerateRequest, db: Session = Depends(get_db)):
    recipes = db.query(models.Recipe).filter(models.Recipe.id.in_(payload.recipe_ids)).all()
    if len(recipes) != len(set(payload.recipe_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more recipes not found")

    items = []
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            item = models.ShoppingListItem(
                recipe_id=recipe.id,
                name=ingredient.name,
                quantity=ingredient.quantity,
                unit=ingredient.unit,
                category=ingredient.category,
            )
            db.add(item)
            items.append(item)
    db.commit()
    for item in items:
        db.refresh(item)
    return items


@router.post("", response_model=schemas.ShoppingListItemRead, status_code=status.HTTP_201_CREATED)
def add_item(payload: schemas.ShoppingListItemCreate, db: Session = Depends(get_db)):
    item = models.ShoppingListItem(**payload.model_dump())
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
