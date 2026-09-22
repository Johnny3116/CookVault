from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import ClassVar

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

from app.models import (
    AlternateType,
    ShoppingAisle,
    DraftStatus,
    ImportMethod,
    IngredientCategory,
    MealPlanMode,
    MealType,
    SourceType,
)

class PatchModel(BaseModel):
    """Base for PATCH payloads.

    Every field is optional, which is what makes a partial update partial --
    but optional is not the same as nullable. `{"title": null}` is *set*, so it
    survives `exclude_unset` and reaches a NOT NULL column as None, where the
    database raises IntegrityError and FastAPI reports it as a 500: the app
    blaming itself for what was really a bad request.

    Subclasses list the fields backed by NOT NULL columns. Nullable columns are
    deliberately absent from that list, because clearing one is a legitimate
    edit -- `source_url: null` means "forget where this came from".
    """

    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_null_for_non_nullable(self):
        nulled = sorted(
            field
            for field in self.non_nullable
            # `in model_fields_set` is the whole distinction: sent-as-null, not
            # merely absent.
            if field in self.model_fields_set and getattr(self, field) is None
        )
        if nulled:
            raise ValueError(f"these fields cannot be null: {', '.join(nulled)}")
        return self


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


class IngredientUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"name", "category", "position"})

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


class StepUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"order", "instruction_text"})

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


class AlternateUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"type", "original_value", "alternate_value"})

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


class RecipeUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"title", "source_type", "cook_methods", "tags", "is_favorite"})

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
    # Derived from the cook log, never stored: a counter and a log can
    # disagree, and then something has to decide which one lied.
    times_cooked: int = 0
    last_cooked_on: CalendarDate | None = None


class RecipeDetail(RecipeSummary):
    ingredients: list[IngredientRead] = []
    steps: list[StepRead] = []
    alternates: list[AlternateRead] = []
    # Present when the response has been scaled away from the stored recipe.
    # The stored recipe is always canonical; scaling happens at read time.
    scaled_to_servings: int | None = None
    applied_scale: Decimal | None = None
    # Where this recipe came from, when it wasn't simply typed in.
    provenance: ProvenanceRead | None = None


class ShoppingListItemBase(BaseModel):
    name: str
    quantity: Decimal | None = None
    unit: str | None = None
    category: IngredientCategory = IngredientCategory.misc
    is_checked: bool = False


class ShoppingListItemCreate(ShoppingListItemBase):
    recipe_id: uuid.UUID | None = None


class ShoppingListItemUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"name", "category", "is_checked"})

    # Nullable on purpose: clearing it hands the line back to the rules.
    aisle_override: ShoppingAisle | None = None

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
    # What the rules (or an override) put this line in. Computed per response
    # rather than stored, so correcting a rule corrects every existing line.
    aisle: ShoppingAisle = ShoppingAisle.other
    aisle_override: ShoppingAisle | None = None


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


class MealPlanEntryUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"date"})

    date: CalendarDate | None = None
    meal_type: MealType | None = None
    servings: int | None = None


class MealPlanEntryRead(MealPlanEntryBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class ProvenanceBase(BaseModel):
    """Where a draft or recipe came from, and who or what shaped it."""

    source_type: SourceType = SourceType.manual
    source_url: str | None = None
    source_title: str | None = None
    import_method: ImportMethod = ImportMethod.manual
    # The raw source, kept apart from what was extracted out of it, so the two
    # can still be compared later.
    original_text: str | None = None
    extracted_payload: dict | None = None
    agent_model: str | None = None
    agent_version: str | None = None


class ProvenanceCreate(ProvenanceBase):
    pass


class ProvenanceRead(ProvenanceBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    draft_id: uuid.UUID | None = None
    recipe_id: uuid.UUID | None = None
    imported_at: datetime


class DraftIssueRead(BaseModel):
    """One problem with a proposed recipe.

    `error` blocks promotion; `warning` is "look at this before you approve it"
    -- an unconvertible unit, an ingredient listed twice.
    """

    severity: str
    field: str
    message: str


class DraftValidation(BaseModel):
    ok: bool
    issues: list[DraftIssueRead] = []


class RecipeDraftCreate(BaseModel):
    title: str | None = None
    # Shaped like RecipeCreate, but not typed as it: a draft is allowed to be
    # wrong on arrival. Rejecting it at the door would mean the payloads most
    # worth reviewing are the ones that can never be stored.
    payload: dict = {}
    provenance: ProvenanceCreate | None = None


class RecipeDraftUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"payload"})

    title: str | None = None
    payload: dict | None = None


class RecipeDraftSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str | None = None
    status: DraftStatus
    promoted_recipe_id: uuid.UUID | None = None
    promoted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RecipeDraftDetail(RecipeDraftSummary):
    payload: dict = {}
    provenance: ProvenanceRead | None = None


class ImportUrlRequest(BaseModel):
    """Import a recipe page. The result is always a draft, never a recipe."""

    url: AnyHttpUrl
    source_type: SourceType = SourceType.web
    source_title: str | None = None


class ImportPasteRequest(BaseModel):
    """Import pasted recipe text."""

    text: str
    # Overrides whatever the parser guessed from the first line.
    title: str | None = None
    source_type: SourceType = SourceType.manual
    source_title: str | None = None
    source_url: str | None = None


class AisleRuleBase(BaseModel):
    """One "this word means that aisle" mapping."""

    term: str
    aisle: ShoppingAisle


class AisleRuleCreate(AisleRuleBase):
    pass


class AisleRuleUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"term", "aisle"})

    term: str | None = None
    aisle: ShoppingAisle | None = None


class AisleRuleRead(AisleRuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime


class AisleResolution(BaseModel):
    """What the rules make of a name, and which rule decided it -- so a
    surprising answer can be traced to the row that caused it."""

    name: str
    aisle: ShoppingAisle
    matched_term: str | None = None


class CookLogBase(BaseModel):
    """One occasion of cooking something."""

    cooked_on: CalendarDate
    # What you actually made, which is not always what you planned. Bounded
    # here as well as by the check constraint, so a nonsensical value is a 422
    # about the request rather than a 500 from the database.
    servings_made: int | None = Field(default=None, gt=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class CookLogCreate(CookLogBase):
    # Defaults to today, because the overwhelmingly common case is logging a
    # meal you have just eaten.
    cooked_on: CalendarDate | None = None


class CookLogUpdate(PatchModel):
    non_nullable: ClassVar[frozenset[str]] = frozenset({"cooked_on"})

    cooked_on: CalendarDate | None = None
    servings_made: int | None = Field(default=None, gt=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None


class CookLogRead(CookLogBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recipe_id: uuid.UUID
    created_at: datetime


class CookLogEntry(CookLogRead):
    """A log line with the recipe's title, for the "recently cooked" feed --
    otherwise reading it means a lookup per row."""

    recipe_title: str
