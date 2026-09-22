from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import AlternateType, IngredientCategory, MealPlanMode, MealType, SourceType

# A field named `date` that carries a default puts `date = <default>` in its
# class body, which shadows the imported type when the annotation is resolved.
# Annotate such fields with this alias instead.
CalendarDate = date


class IngredientBase(BaseModel):
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    category: IngredientCategory = IngredientCategory.misc


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(BaseModel):
    """Every field optional -- this is what makes PATCH actually partial."""

    name: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    category: IngredientCategory | None = None
    position: int | None = None


class IngredientRead(IngredientBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipe_id: uuid.UUID
    position: int


class StepBase(BaseModel):
    order: int
    instruction_text: str
    temperature: str | None = None
    duration: str | None = None
    notes: str | None = None


class StepCreate(StepBase):
    pass


class StepUpdate(BaseModel):
    """Every field optional -- this is what makes PATCH actually partial."""

    order: int | None = None
    instruction_text: str | None = None
    temperature: str | None = None
    duration: str | None = None
    notes: str | None = None


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


class AlternateUpdate(BaseModel):
    """Every field optional -- this is what makes PATCH actually partial."""

    type: AlternateType | None = None
    original_value: str | None = None
    alternate_value: str | None = None
    notes: str | None = None


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


class RecipeFacets(BaseModel):
    """Distinct tag and cook-method values present in the library."""

    tags: list[str] = []
    cook_methods: list[str] = []


class RecipeReplace(RecipeCreate):
    """Body for PUT /recipes/{id} -- replaces the recipe and all its children."""


class RecipeSummary(RecipeBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class RecipeDetail(RecipeSummary):
    ingredients: list[IngredientRead] = []
    steps: list[StepRead] = []
    alternates: list[AlternateRead] = []
    # Present when the response has been scaled away from the stored recipe.
    # The stored recipe is always canonical; scaling happens at read time.
    scaled_to_servings: int | None = None
    applied_scale: Decimal | None = None


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
    is_generated: bool = False


class ShoppingListGenerateRequest(BaseModel):
    """What to shop for: ad-hoc recipes, a span of the meal plan, or both.

    Meal-plan entries carry their own planned servings, so generating from a
    week buys the amounts actually planned. Bare recipe_ids are bought as the
    recipe is written.
    """

    recipe_ids: list[uuid.UUID] = []
    start: date | None = None
    end: date | None = None


class MealPlanEntryBase(BaseModel):
    date: date
    recipe_id: uuid.UUID
    mode: MealPlanMode = MealPlanMode.manual
    meal_type: MealType | None = None
    # Servings wanted on the day; None means "as the recipe is written".
    servings: int | None = None


class MealPlanEntryCreate(MealPlanEntryBase):
    pass


class MealPlanEntryUpdate(BaseModel):
    date: CalendarDate | None = None
    meal_type: MealType | None = None
    servings: int | None = None


class MealPlanEntryRead(MealPlanEntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
