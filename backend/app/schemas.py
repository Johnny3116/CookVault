from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import AlternateType, IngredientCategory, MealPlanMode, SourceType


class IngredientBase(BaseModel):
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    category: IngredientCategory = IngredientCategory.misc


class IngredientCreate(IngredientBase):
    pass


class IngredientRead(IngredientBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipe_id: uuid.UUID


class StepBase(BaseModel):
    order: int
    instruction_text: str
    temperature: str | None = None
    duration: str | None = None
    notes: str | None = None


class StepCreate(StepBase):
    pass


class StepRead(StepBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipe_id: uuid.UUID


class AlternateBase(BaseModel):
    type: AlternateType
    original_value: str
    alternate_value: str
    notes: str | None = None


class AlternateCreate(AlternateBase):
    pass


class AlternateRead(AlternateBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipe_id: uuid.UUID


class RecipeBase(BaseModel):
    title: str
    source_type: SourceType = SourceType.manual
    source_url: str | None = None
    cook_methods: list[str] = []
    prep_time: int | None = None
    cook_time: int | None = None
    servings: int | None = None
    estimated_cost: Decimal | None = None
    tags: list[str] = []
    is_favorite: bool = False


class RecipeCreate(RecipeBase):
    ingredients: list[IngredientCreate] = []
    steps: list[StepCreate] = []
    alternates: list[AlternateCreate] = []


class RecipeUpdate(BaseModel):
    title: str | None = None
    source_type: SourceType | None = None
    source_url: str | None = None
    cook_methods: list[str] | None = None
    prep_time: int | None = None
    cook_time: int | None = None
    servings: int | None = None
    estimated_cost: Decimal | None = None
    tags: list[str] | None = None
    is_favorite: bool | None = None


class RecipeSummary(RecipeBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RecipeDetail(RecipeSummary):
    ingredients: list[IngredientRead] = []
    steps: list[StepRead] = []
    alternates: list[AlternateRead] = []


class ShoppingListItemBase(BaseModel):
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    category: IngredientCategory = IngredientCategory.misc
    is_checked: bool = False


class ShoppingListItemCreate(ShoppingListItemBase):
    recipe_id: uuid.UUID | None = None


class ShoppingListItemUpdate(BaseModel):
    name: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    category: IngredientCategory | None = None
    is_checked: bool | None = None


class ShoppingListItemRead(ShoppingListItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipe_id: uuid.UUID | None = None


class ShoppingListGenerateRequest(BaseModel):
    recipe_ids: list[uuid.UUID]


class MealPlanEntryBase(BaseModel):
    date: date
    recipe_id: uuid.UUID
    mode: MealPlanMode = MealPlanMode.manual


class MealPlanEntryCreate(MealPlanEntryBase):
    pass


class MealPlanEntryRead(MealPlanEntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
