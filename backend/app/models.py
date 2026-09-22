from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy import select
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

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


class DraftStatus(str, enum.Enum):
    """Where a draft is in the review cycle.

    The point of `ready` is that validation is a recorded event, not a live
    computation: a draft is only promotable because CookVault said so about
    *this* payload. Editing the payload drops it back to `draft`.
    """

    draft = "draft"
    ready = "ready"
    promoted = "promoted"
    discarded = "discarded"


class ImportMethod(str, enum.Enum):
    """How the content physically arrived, separate from where it came from.

    `source_type` says "a YouTube video"; `import_method` says whether a human
    typed it out or a model extracted it. Only the second one tells you how
    much to trust the numbers.
    """

    manual = "manual"
    paste = "paste"
    url_fetch = "url_fetch"
    agent = "agent"


class ShoppingAisle(str, enum.Enum):
    """Where a thing lives in the shop.

    Deliberately not the same axis as IngredientCategory. "Spices & sauces" is
    about what a thing *is* when you cook with it; "bakery" is about where you
    walk to pick it up. Chicken stock is a pantry ingredient and a pantry-aisle
    item; fresh parsley is a spice_sauce ingredient sitting in produce. Folding
    the two together loses one of them.
    """

    produce = "produce"
    meat_seafood = "meat_seafood"
    dairy_eggs = "dairy_eggs"
    bakery = "bakery"
    frozen = "frozen"
    pantry = "pantry"
    drinks = "drinks"
    household = "household"
    other = "other"


class MealType(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


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
    # The FK is ON DELETE CASCADE, so the database is what actually removes a
    # deleted recipe's history -- these options keep the session's view of it
    # consistent, they are not the guarantee.
    cook_log: Mapped[list[CookLog]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CookLog.cooked_on.desc()",
    )
    # Set when the recipe was promoted from a draft, or imported. Deleting the
    # recipe deletes this row (the FK cascades), which also takes it off the
    # draft it came from -- deliberate: erasing the recipe erases the import.
    provenance: Mapped[RecipeProvenance | None] = relationship(
        back_populates="recipe",
        uselist=False,
        foreign_keys="RecipeProvenance.recipe_id",
        passive_deletes=True,
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
    # Distinguishes rows built by /generate from ones typed in by hand.
    # recipe_id can't carry this: merging an ingredient that came from three
    # recipes leaves no single recipe to point at.
    is_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Set only when overriding what the rules resolve to. Null means "whatever
    # the rules say", so fixing a rule fixes every item that relied on it --
    # the same reason unit conversion is computed rather than stored.
    aisle_override: Mapped[ShoppingAisle | None] = mapped_column(
        Enum(ShoppingAisle, name="shopping_aisle"), nullable=True
    )

    recipe: Mapped[Recipe | None] = relationship(back_populates="shopping_list_items")


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    recipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    mode: Mapped[MealPlanMode] = mapped_column(
        Enum(MealPlanMode, name="meal_plan_mode"), default=MealPlanMode.manual, nullable=False
    )
    meal_type: Mapped[MealType | None] = mapped_column(
        Enum(MealType, name="meal_type"), nullable=True
    )
    # Servings wanted on this date. None means "as the recipe is written".
    # Stored as a target rather than a multiplier so it stays meaningful if the
    # recipe's own yield is later corrected.
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="meal_plan_entries")


class RecipeDraft(Base):
    """A proposed recipe that is not in the cookbook yet.

    Drafts exist so that nothing reaches `recipes` without passing validation
    and then a human. The lifecycle -- create, edit, validate, promote -- is
    built and proven by hand first; when an agent is eventually allowed to
    write here, it gets exactly the same door as the "new draft" button, and
    no other.
    """

    __tablename__ = "recipe_drafts"
    # Declared here as well as in the migration so autogenerate doesn't see the
    # index as drift and propose dropping it.
    __table_args__ = (Index("ix_recipe_drafts_status_updated", "status", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Half-formed by definition: a draft may not have decided on a title yet.
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        Enum(DraftStatus, name="draft_status"), default=DraftStatus.draft, nullable=False
    )
    # The normalized proposal, shaped like RecipeCreate. Deliberately schemaless
    # at rest: a draft is allowed to be wrong -- that is what validation is for
    # -- and columns would reject the very payloads worth reviewing.
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    promoted_recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    promoted_recipe: Mapped[Recipe | None] = relationship()
    provenance: Mapped[RecipeProvenance | None] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        uselist=False,
        foreign_keys="RecipeProvenance.draft_id",
    )


class RecipeProvenance(Base):
    """Where a draft or recipe came from, and who or what shaped it.

    The raw text and the extracted structure are stored separately on purpose.
    "Did the transcript actually say two teaspoons, or did the model decide
    that?" is unanswerable once the two are merged, and it is exactly the
    question worth asking about an imported recipe.

    A row can point at a draft, a recipe, or -- after promotion -- both, which
    is how a recipe keeps its history once the draft it came from is done.
    """

    __tablename__ = "recipe_provenance"
    __table_args__ = (
        CheckConstraint(
            "draft_id IS NOT NULL OR recipe_id IS NOT NULL",
            name="ck_recipe_provenance_has_subject",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recipe_drafts.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"), default=SourceType.manual, nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    import_method: Mapped[ImportMethod] = mapped_column(
        Enum(ImportMethod, name="import_method"), default=ImportMethod.manual, nullable=False
    )
    # The raw thing: a transcript, a pasted block, a page's text.
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the extractor produced from it, before any human edit.
    extracted_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    draft: Mapped[RecipeDraft | None] = relationship(back_populates="provenance", foreign_keys=[draft_id])
    recipe: Mapped[Recipe | None] = relationship(back_populates="provenance", foreign_keys=[recipe_id])


class AisleRule(Base):
    """One "this word means that aisle" mapping.

    Rows rather than a dict in the source, because the right answer is personal
    and changes with the shop: it is data, so it is editable at runtime without
    a deploy. The seeded set in migration 0006 is a starting point, not a
    fixture the code depends on.
    """

    __tablename__ = "aisle_rules"
    __table_args__ = (Index("ix_aisle_rules_term", "term", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Matched case-insensitively as a whole word against an item's name.
    term: Mapped[str] = mapped_column(String(100), nullable=False)
    aisle: Mapped[ShoppingAisle] = mapped_column(
        Enum(ShoppingAisle, name="shopping_aisle"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CookLog(Base):
    """One occasion of actually cooking a recipe.

    The point of keeping these is the questions they answer: what have I not
    made in ages, what do I come back to, and what did I think last time. The
    rating and note belong to the occasion rather than to the recipe, because
    "too salty" is about the night you made it, not about the recipe forever.
    """

    __tablename__ = "cook_log"
    __table_args__ = (Index("ix_cook_log_recipe_cooked_on", "recipe_id", "cooked_on"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    cooked_on: Mapped[date] = mapped_column(Date, nullable=False)
    # What you actually made, which is not always what you planned.
    servings_made: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recipe: Mapped[Recipe] = relationship(back_populates="cook_log")


# Derived from the log rather than kept as counters on the recipe. A counter
# and a log can disagree, and then something has to decide which one lied;
# these two cannot drift because there is only one source.
Recipe.times_cooked = column_property(
    select(func.count(CookLog.id))
    .where(CookLog.recipe_id == Recipe.id)
    .correlate_except(CookLog)
    .scalar_subquery()
)
Recipe.last_cooked_on = column_property(
    select(func.max(CookLog.cooked_on))
    .where(CookLog.recipe_id == Recipe.id)
    .correlate_except(CookLog)
    .scalar_subquery()
)
