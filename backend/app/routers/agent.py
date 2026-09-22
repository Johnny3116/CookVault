"""The tool surface Agent Zero is given, and the shape of what it may do.

CookVault is the server here, not the client. That inversion is the whole
design of this file, and it is what made Phase 2 buildable: an agent calling
*in* needs no guess about anyone else's wire format, and every write it can
attempt is one CookVault wrote and validates. The outbound half -- CookVault
calling Agent Zero -- is still unbuilt for exactly the opposite reason; see
`app/agent_zero_client.py`.

**AI proposes. CookVault validates. John approves.** In endpoints:

- The agent reads (`search_recipes`, `get_recipe`) and parses
  (`parse_recipe_source`, which is CookVault's own deterministic parser, no
  model involved).
- The agent *proposes* by creating drafts -- recipe drafts and meal plan
  drafts. A draft is a proposal, not a change.
- The agent cannot promote a draft, write a recipe, write a meal plan entry,
  delete anything, touch the shopping list, the pantry, the aisle rules or a
  backup. Those endpoints are not mounted here and this router mounts nothing
  outside its own prefix. `test_agent_surface.py` asserts the whole list.

The agent also cannot edit a draft a human already started, or one that has
been settled. Review is a one-way door: once John has promoted or discarded
something, the agent does not get to reopen it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas, schemas_agent as sa
from app.agent_auth import require_agent
from app.db import get_db
from app.services import recipe_search
from app.routers.drafts import _SETTLED, build_draft
from app.services.drafts import has_errors, validate_payload
from app.services.recipe_text import parse_recipe_text
from app.services.web_import import SourceFetchError, fetch_page, payload_from_page

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_agent)])


# What this surface promises, in the response itself. An agent should be able
# to find out what it cannot do without discovering it through a 403.
GUARANTEES = [
    "Writes create drafts only. Nothing here changes the cookbook, the meal plan, "
    "the shopping list or the pantry.",
    "Promotion and discard are John's alone; they are not on this surface.",
    "Drafts created here are recorded with import_method=agent and cannot claim otherwise.",
    "A draft that has been promoted or discarded can no longer be edited by anyone.",
    "A draft not created through this surface cannot be edited through it.",
    "Nothing is deleted through this surface.",
]


def _summary(recipe: models.Recipe) -> sa.AgentRecipeSummary:
    total = None
    if recipe.prep_time is not None or recipe.cook_time is not None:
        total = (recipe.prep_time or 0) + (recipe.cook_time or 0)
    return sa.AgentRecipeSummary(
        id=recipe.id,
        title=recipe.title,
        tags=list(recipe.tags or []),
        cook_methods=list(recipe.cook_methods or []),
        prep_time=recipe.prep_time,
        cook_time=recipe.cook_time,
        total_time=total,
        servings=recipe.servings,
        estimated_cost=recipe.estimated_cost,
        is_favorite=recipe.is_favorite,
        times_cooked=recipe.times_cooked,
        last_cooked_on=recipe.last_cooked_on,
    )


def _issues(payload: dict) -> tuple[bool, list[schemas.DraftIssueRead]]:
    issues = validate_payload(payload)
    return (
        not has_errors(issues),
        [
            schemas.DraftIssueRead(severity=i.severity, field=i.field, message=i.message)
            for i in issues
        ],
    )


# --------------------------------------------------------------------------
# the contract, served by the thing that implements it
# --------------------------------------------------------------------------

TOOLS: list[sa.ToolDescriptor] = [
    sa.ToolDescriptor(
        name="manifest",
        method="GET",
        path="/agent/manifest",
        writes=False,
        summary="This document: the tools available and what they are not allowed to do.",
    ),
    sa.ToolDescriptor(
        name="parse_recipe_source",
        method="POST",
        path="/agent/parse-recipe-source",
        writes=False,
        summary=(
            "Read raw recipe text, or fetch a recipe page, with CookVault's deterministic "
            "parser. No model involved and nothing is stored."
        ),
    ),
    sa.ToolDescriptor(
        name="search_recipes",
        method="POST",
        path="/agent/search-recipes",
        writes=False,
        summary="Search the saved library by tags, time, cost, ingredients and cooking history.",
    ),
    sa.ToolDescriptor(
        name="get_recipe",
        method="GET",
        path="/agent/recipes/{recipe_id}",
        writes=False,
        summary="One saved recipe in full, with ingredients, steps, alternates and provenance.",
    ),
    sa.ToolDescriptor(
        name="create_recipe_draft",
        method="POST",
        path="/agent/recipe-drafts",
        writes=True,
        summary=(
            "Propose a recipe. It lands in John's review queue, recorded as agent-authored, "
            "and reaches the cookbook only if he promotes it."
        ),
    ),
    sa.ToolDescriptor(
        name="get_recipe_draft",
        method="GET",
        path="/agent/recipe-drafts/{draft_id}",
        writes=False,
        summary="Read back one of your own proposals, with CookVault's current verdict on it.",
    ),
    sa.ToolDescriptor(
        name="update_recipe_draft",
        method="PATCH",
        path="/agent/recipe-drafts/{draft_id}",
        writes=True,
        summary="Revise one of your own proposals, while it is still unsettled.",
    ),
]


@router.get("/manifest", response_model=sa.Manifest)
def manifest():
    """The tool list, from the server that implements it.

    Served rather than written down because a document describing an API is a
    document that will eventually describe a different API. `test_agent_surface`
    asserts this list and the mounted routes are the same set, so the two
    cannot drift apart quietly.
    """
    return sa.Manifest(
        contract_version=sa.CONTRACT_VERSION, guarantees=GUARANTEES, tools=TOOLS
    )


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


@router.post("/parse-recipe-source", response_model=sa.ParseSourceResponse)
def parse_recipe_source(payload: sa.ParseSourceRequest):
    """CookVault's parser, offered as a tool. Stores nothing.

    Two reasons this exists rather than letting the agent do all the reading
    itself. It gives the agent a second opinion it can disagree with -- and a
    disagreement about a quantity is worth putting in front of John. And it
    routes every fetch through `check_url`, so a link the agent was handed by a
    stranger still cannot make CookVault fetch from inside the Tailscale
    network.
    """
    if (payload.text is None) == (payload.url is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Send exactly one of text or url.",
        )

    if payload.text is not None:
        if not payload.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="There's no text to parse."
            )
        parsed = parse_recipe_text(payload.text)
        method, source_text = "paste", payload.text
    else:
        try:
            page_html = fetch_page(str(payload.url))
        except SourceFetchError as exc:
            # The URL was bad, private or unreachable: the caller's problem to
            # fix, so 400 rather than a 500 that reads like CookVault broke.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        parsed, source_text, from_jsonld = payload_from_page(page_html)
        method = "jsonld" if from_jsonld else "page_text"

    _, issues = _issues(parsed)
    return sa.ParseSourceResponse(
        payload=parsed, method=method, source_text=source_text, issues=issues
    )


@router.post("/search-recipes", response_model=sa.SearchRecipesResponse)
def search_recipes(payload: sa.SearchRecipesRequest, db: Session = Depends(get_db)):
    """The library, narrowed.

    `total_matched` is counted before the limit is applied. Without it the
    agent cannot tell "these are the only three recipes that fit" from "here
    are three of ninety", and those call for different answers.
    """
    if payload.sort not in recipe_search.SORTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"sort must be one of: {', '.join(recipe_search.SORTS)}",
        )

    filters = recipe_search.RecipeFilters(
        favorite=payload.favorite,
        tags=payload.tags,
        cook_methods=payload.cook_methods,
        includes_ingredients=payload.includes_ingredients,
        max_total_time=payload.max_total_time,
        max_cost=payload.max_cost,
        text=payload.text,
        not_cooked_since=payload.not_cooked_since,
        never_cooked=payload.never_cooked,
        sort=payload.sort,
    )
    stmt = recipe_search.build_query(filters)
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = db.execute(stmt.limit(payload.limit)).scalars().all()
    return sa.SearchRecipesResponse(
        total_matched=total, results=[_summary(r) for r in rows]
    )


@router.get("/recipes/{recipe_id}", response_model=schemas.RecipeDetail)
def get_recipe(recipe_id: uuid.UUID, db: Session = Depends(get_db)):
    """One recipe in full.

    The same shape the web UI reads, provenance included: if the agent is going
    to reason about a recipe it should see that a model wrote it in the first
    place.
    """
    recipe = db.get(models.Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


# --------------------------------------------------------------------------
# proposing
# --------------------------------------------------------------------------


def _agent_draft_or_404(draft_id: uuid.UUID, db: Session) -> models.RecipeDraft:
    """The agent's own draft, or nothing.

    A draft John wrote is invisible here rather than forbidden: 404 and 403
    differ only in whether they confirm the row exists, and there is no reason
    for this surface to confirm anything about drafts it does not own.
    """
    draft = db.get(models.RecipeDraft, draft_id)
    if draft is None or draft.created_by != models.DraftAuthor.agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


def _draft_response(draft: models.RecipeDraft) -> sa.AgentDraftResponse:
    valid, issues = _issues(draft.payload)
    return sa.AgentDraftResponse(
        id=draft.id,
        status=draft.status,
        title=draft.title,
        payload=draft.payload,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        valid=valid,
        issues=issues,
    )


def _revalidate(draft: models.RecipeDraft) -> None:
    """Record the verdict on the payload as it now stands.

    Done on every write rather than left to a second call, because the agent's
    next move depends on the answer and a round trip it can skip is a round
    trip it will skip. It is a convenience, not the gate -- promotion validates
    again and does not trust this.
    """
    draft.status = (
        models.DraftStatus.ready
        if not has_errors(validate_payload(draft.payload))
        else models.DraftStatus.draft
    )


@router.post(
    "/recipe-drafts",
    response_model=sa.AgentDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_recipe_draft(payload: sa.CreateRecipeDraftRequest, db: Session = Depends(get_db)):
    """Propose a recipe. It lands in John's review queue and nowhere else.

    An invalid payload is accepted and reported, not refused. A draft is
    allowed to be wrong -- that is the entire reason the queue exists -- and
    rejecting the proposals worth reviewing would leave the agent guessing at
    what CookVault wanted instead of being told.
    """
    provenance = schemas.ProvenanceCreate(
        **payload.provenance.model_dump(),
        # Not the caller's to claim. The one field that says "a model touched
        # this" is worthless if the model can set it to something else.
        import_method=models.ImportMethod.agent,
        # A frozen copy of what the agent proposed, so John can still see it
        # after he has edited the draft into shape.
        extracted_payload=payload.payload,
    )
    draft = build_draft(payload.title, payload.payload, provenance)
    draft.created_by = models.DraftAuthor.agent
    draft.note = payload.note
    _revalidate(draft)

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_response(draft)


@router.get("/recipe-drafts/{draft_id}", response_model=sa.AgentDraftResponse)
def get_recipe_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Read back a proposal, with CookVault's current verdict on it.

    Only the agent's own. Listing the queue is not on this surface: what John
    is working on is not the agent's business.
    """
    return _draft_response(_agent_draft_or_404(draft_id, db))


@router.patch("/recipe-drafts/{draft_id}", response_model=sa.AgentDraftResponse)
def update_recipe_draft(
    draft_id: uuid.UUID, payload: sa.UpdateRecipeDraftRequest, db: Session = Depends(get_db)
):
    """Revise a proposal that hasn't been settled yet.

    Once John has promoted or discarded something the answer is 409: review is
    a one-way door, and an agent that could reopen a decision would make the
    decision provisional.
    """
    draft = _agent_draft_or_404(draft_id, db)
    if draft.status in _SETTLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This draft is {draft.status.value} and can no longer be changed.",
        )

    data = payload.model_dump(exclude_unset=True)
    if "title" in data:
        draft.title = data["title"]
    if "note" in data:
        draft.note = data["note"]
    if data.get("payload") is not None:
        draft.payload = data["payload"]
    _revalidate(draft)

    db.commit()
    db.refresh(draft)
    return _draft_response(draft)
