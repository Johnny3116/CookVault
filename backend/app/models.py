from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SourceType(str, enum.Enum):
    manual = "manual"
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"
    web = "web"


class IngredientCategory(str, enum.Enum):
    raw_ingredient = "raw_ingredient"
    spice_sauce = "spice_sauce"
    pantry_dry_good = "pantry_dry_good"
    misc = "misc"


class AlternateType(str, enum.Enum):
    cook_method = "cook_method"
    ingredient_substitute = "ingredient_substitute"


class MealPlanMode(str, enum.Enum):
    auto = "auto"
    manual = "manual"


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"), default=SourceType.manual, nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    cook_methods: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    prep_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    ingredients: Mapped[list[Ingredient]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="Ingredient.position"
    )
    steps: Mapped[list[Step]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", order_by="Step.order"
    )
    alternates: Mapped[list[Alternate]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    shopping_list_items: Mapped[list[ShoppingListItem]] = relationship(back_populates="recipe")
    # cascade+passive_deletes: meal plan entries require a recipe (recipe_id is
    # NOT NULL), so on recipe delete they must be deleted too, not nullified --
    # matches the FK's ondelete="CASCADE" in the initial migration.
    meal_plan_entries: Mapped[list[MealPlanEntry]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", passive_deletes=True
    )


class Ingredient(Base):
    __tablename__ = "ingredients"
    # Declared here as well as in the migration so autogenerate doesn't see the
    # index as drift and propose dropping it.
    __table_args__ = (Index("ix_ingredients_recipe_position", "recipe_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    # Display order within the recipe. Without it, ingredients come back in
    # UUID order -- i.e. shuffled, and re-shuffled after every edit.
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[IngredientCategory] = mapped_column(
        Enum(IngredientCategory, name="ingredient_category"), default=IngredientCategory.misc, nullable=False
    )

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction_text: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="steps")


class Alternate(Base):
    __tablename__ = "alternates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[AlternateType] = mapped_column(Enum(AlternateType, name="alternate_type"), nullable=False)
    original_value: Mapped[str] = mapped_column(String(255), nullable=False)
    alternate_value: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="alternates")


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[IngredientCategory] = mapped_column(
        Enum(IngredientCategory, name="ingredient_category"), default=IngredientCategory.misc, nullable=False
    )
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    recipe: Mapped[Recipe | None] = relationship(back_populates="shopping_list_items")


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[MealPlanMode] = mapped_column(
        Enum(MealPlanMode, name="meal_plan_mode"), default=MealPlanMode.manual, nullable=False
    )

    recipe: Mapped[Recipe] = relationship(back_populates="meal_plan_entries")
