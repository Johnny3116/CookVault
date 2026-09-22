"""The request and response shapes Agent Zero is coded against.

These live apart from `app/schemas.py` on purpose. Everything in that file is
internal: the web UI ships with the backend, so the two move together and a
field can be renamed in one commit. This file is a contract with a program on
another machine that is *not* redeployed when CookVault is, so changing a name
here breaks something that isn't in this repository.

Keeping it in one readable file is the point -- `GET /agent/manifest` serves
these shapes back, so the agent's configuration can be derived from the running
server instead of transcribed from a doc that goes stale.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.models import DraftStatus, MealType, SourceType
from app.schemas import CalendarDate, DraftIssueRead

# Bumped when a shape here changes in a way that would break an agent coded
# against the previous one. Served by the manifest so the agent can notice.
CONTRACT_VERSION = 1


class AgentRequest(BaseModel):
    """Base for everything the agent sends.

    `extra="forbid"` rather than pydantic's default of quietly dropping unknown
    fields. This is a contract with a program on another machine: a misspelled
    field, or one the agent believes exists and does not, should come back as a
    422 naming it. Ignored input is the failure mode where both sides think the
    call worked and only one of them is right -- and the field most likely to
    be tried is `import_method`, which this surface will never accept.
    """

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# parse_recipe_source
# --------------------------------------------------------------------------


class ParseSourceRequest(AgentRequest):
    """Raw material in, CookVault's own reading of it out.

    Exactly one of `text` or `url`. Offering the parser as a tool means the
    agent can compare what it believes a source says against what the
    deterministic parser saw -- and a disagreement is worth surfacing to John
    rather than resolving silently.
    """

    text: str | None = None
    url: AnyHttpUrl | None = None


class ParseSourceResponse(BaseModel):
    payload: dict
    # How the text was obtained and read: "paste", "jsonld" or "page_text".
    method: str
    # What was parsed, kept so the agent can quote the source rather than
    # paraphrase it.
    source_text: str
    issues: list[DraftIssueRead] = []


# --------------------------------------------------------------------------
# search_recipes / get_recipe
# --------------------------------------------------------------------------


class SearchRecipesRequest(AgentRequest):
    """Narrow the library. Every field is optional and means "don't care".

    `includes_ingredients` is all-of, and is the "use up the chicken" question,
    not "what can I make from only these" -- see services/recipe_search.
    """

    text: str | None = None
    tags: list[str] = []
    cook_methods: list[str] = []
    includes_ingredients: list[str] = []
    max_total_time: int | None = Field(default=None, gt=0)
    max_cost: Decimal | None = Field(default=None, gt=0)
    favorite: bool | None = None
    not_cooked_since: CalendarDate | None = None
    never_cooked: bool = False
    sort: str = "updated"
    limit: int = Field(default=25, ge=1, le=100)


class AgentRecipeSummary(BaseModel):
    """Enough for the agent to choose between recipes without fetching each.

    Deliberately not the UI's summary: this one carries total_time and the cook
    log's answers, because those are what "a quick midweek thing we haven't had
    in a while" is actually made of.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    tags: list[str] = []
    cook_methods: list[str] = []
    prep_time: int | None = None
    cook_time: int | None = None
    total_time: int | None = None
    servings: int | None = None
    estimated_cost: Decimal | None = None
    is_favorite: bool = False
    times_cooked: int = 0
    last_cooked_on: CalendarDate | None = None


class SearchRecipesResponse(BaseModel):
    # The number matched before `limit` was applied, so the agent can tell
    # "these are the only three" from "here are three of ninety".
    total_matched: int
    results: list[AgentRecipeSummary]


# --------------------------------------------------------------------------
# create_recipe_draft / update_recipe_draft
# --------------------------------------------------------------------------


class AgentProvenance(AgentRequest):
    """Where the agent got this, and what did the reading.

    `import_method` is not offered: anything arriving through this surface is
    `agent`, and letting the caller claim otherwise would make the one field
    that says "a model touched this" unreliable.
    """

    source_type: SourceType = SourceType.manual
    source_url: str | None = Field(default=None, max_length=2048)
    source_title: str | None = Field(default=None, max_length=512)
    # The raw text the payload was derived from. Stored separately from the
    # payload so "did the transcript say two teaspoons, or did the model decide
    # that?" stays answerable.
    original_text: str | None = None
    agent_model: str | None = Field(default=None, max_length=255)
    agent_version: str | None = Field(default=None, max_length=64)


class CreateRecipeDraftRequest(AgentRequest):
    title: str | None = Field(default=None, max_length=255)
    payload: dict
    provenance: AgentProvenance = AgentProvenance()
    # Free text for the reviewer: why this recipe, what the agent was unsure
    # about. It goes to John, not into the recipe.
    note: str | None = None


class UpdateRecipeDraftRequest(AgentRequest):
    title: str | None = Field(default=None, max_length=255)
    payload: dict | None = None
    note: str | None = None


class AgentDraftResponse(BaseModel):
    """What came back, and what CookVault thinks of it.

    The validation result is included on every write rather than left to a
    separate call, because the agent's next action depends on it and a round
    trip it can skip is a round trip it will skip.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: DraftStatus
    title: str | None = None
    payload: dict
    created_at: datetime
    updated_at: datetime
    valid: bool
    issues: list[DraftIssueRead] = []


# --------------------------------------------------------------------------
# suggest_meal_plan / create_meal_plan_draft
# --------------------------------------------------------------------------


class SuggestMealPlanRequest(AgentRequest):
    start: CalendarDate
    days: int = Field(default=7, ge=1, le=28)
    meal_type: MealType = MealType.dinner
    # Candidates per day. More gives the agent room to balance a week; it is
    # not a promise that any of them are good.
    per_day: int = Field(default=5, ge=1, le=20)
    max_total_time: int | None = Field(default=None, gt=0)
    max_cost: Decimal | None = Field(default=None, gt=0)
    tags: list[str] = []
    exclude_recipe_ids: list[uuid.UUID] = []


class MealCandidate(BaseModel):
    recipe: AgentRecipeSummary
    # Higher is a better fit for "we have not had this in a while". The score
    # is explainable on purpose -- see services/meal_planning.
    score: float
    reason: str


class DaySuggestion(BaseModel):
    date: CalendarDate
    candidates: list[MealCandidate]


class SuggestMealPlanResponse(BaseModel):
    days: list[DaySuggestion]
    note: str


class ProposedMeal(AgentRequest):
    date: CalendarDate
    recipe_id: uuid.UUID
    meal_type: MealType = MealType.dinner
    servings: int | None = Field(default=None, gt=0)
    # Why this recipe on this day. Shown to John next to the meal, because a
    # plan you cannot interrogate is one you override out of habit.
    reason: str | None = None


class CreateMealPlanDraftRequest(AgentRequest):
    title: str | None = Field(default=None, max_length=255)
    meals: list[ProposedMeal]
    note: str | None = None
    agent_model: str | None = Field(default=None, max_length=255)
    agent_version: str | None = Field(default=None, max_length=64)


class MealPlanDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: DraftStatus
    title: str | None = None
    note: str | None = None
    meals: list[ProposedMeal]
    covers_from: CalendarDate | None = None
    covers_to: CalendarDate | None = None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------
# the manifest
# --------------------------------------------------------------------------


class ToolDescriptor(BaseModel):
    name: str
    method: str
    path: str
    writes: bool
    summary: str


class Manifest(BaseModel):
    contract_version: int
    # Stated rather than implied: an agent reading this should know what it is
    # not able to do before it tries.
    guarantees: list[str]
    tools: list[ToolDescriptor]
