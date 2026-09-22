"""The calendar, and the queue of proposed weeks waiting on it.

Manual planning is direct: John picks a recipe for a day and it is planned.
Auto planning is not, and deliberately: a proposed week lands in
`meal_plan_drafts` and becomes real entries only when he approves it. That is
the same shape as recipe drafts, for the same reason -- something that guessed
at an answer should not be able to write it down.

Approving is also the only way an entry is ever recorded as `auto`. A mode
anyone could set would stop being a record of where the plan came from.
"""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.services import meal_planning

router = APIRouter(prefix="/meal-plan", tags=["meal-plan"], dependencies=[Depends(require_auth)])

_SETTLED = (models.DraftStatus.promoted, models.DraftStatus.discarded)


@router.get("", response_model=list[schemas.MealPlanEntryRead])
def list_entries(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)):
    query = db.query(models.MealPlanEntry)
    if start is not None:
        query = query.filter(models.MealPlanEntry.date >= start)
    if end is not None:
        query = query.filter(models.MealPlanEntry.date <= end)
    return query.order_by(models.MealPlanEntry.date).all()


@router.post("", response_model=schemas.MealPlanEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: schemas.MealPlanEntryCreate, db: Session = Depends(get_db)):
    if payload.mode == models.MealPlanMode.auto:
        # `auto` is a record of having come from an approved plan, not a label
        # to apply. If anyone could set it, it would stop being an answer to
        # "where did this week come from?".
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Auto entries come from approving a proposed plan, not from being labelled "
                "as one. Use POST /meal-plan/auto-fill, or approve a plan draft."
            ),
        )
    entry = models.MealPlanEntry(**payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# --------------------------------------------------------------------------
# proposed weeks
#
# Declared before /{entry_id} so "drafts" is not read as an entry id.
# --------------------------------------------------------------------------


def _get_plan_or_404(draft_id: uuid.UUID, db: Session) -> models.MealPlanDraft:
    draft = db.get(models.MealPlanDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan draft not found")
    return draft


@router.post(
    "/auto-fill",
    response_model=schemas.MealPlanDraftDetail,
    status_code=status.HTTP_201_CREATED,
)
def auto_fill(payload: schemas.AutoFillRequest, db: Session = Depends(get_db)):
    """Propose a week from the cook log. Plans nothing by itself.

    No model is involved. "Diverse" is arithmetic over the log -- how long
    since each recipe was last made -- and doing it here means the answer is
    explainable and the same twice. Every meal comes with the sentence that
    put it there.

    The result is a draft. What CookVault cannot judge is whether it is a good
    week, so it asks.
    """
    dates = meal_planning.dates_from(payload.start, payload.days)
    ranked = meal_planning.rank(
        db,
        on=payload.start,
        window=(dates[0], dates[-1]),
        max_total_time=payload.max_total_time,
        max_cost=payload.max_cost,
        tags=payload.tags,
    )
    if not ranked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recipes match those filters, so there's nothing to plan.",
        )

    # One recipe per day, taken in rank order: the top candidate for each day
    # after dealing, which is what produces a different recipe each day rather
    # than the same best one seven times.
    dealt = meal_planning.deal(ranked, payload.days, per_day=1)
    meals = [
        {
            "date": day.isoformat(),
            "recipe_id": str(candidates[0].recipe.id),
            "meal_type": payload.meal_type.value,
            "servings": payload.servings,
            "reason": candidates[0].reason,
        }
        for day, candidates in zip(dates, dealt)
        if candidates
    ]

    note = f"Proposed from {len(ranked)} eligible recipes, ordered by how long since each was last cooked."
    if len(meals) < payload.days:
        note += f" Only {len(meals)} of {payload.days} days could be filled without repeating."

    draft = models.MealPlanDraft(
        title=payload.title or f"Week of {payload.start.isoformat()}",
        created_by=models.DraftAuthor.human,
        meals=meals,
        note=note,
        status=models.DraftStatus.ready,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/drafts", response_model=list[schemas.MealPlanDraftSummary])
def list_plan_drafts(
    status_filter: models.DraftStatus | None = None, db: Session = Depends(get_db)
):
    stmt = select(models.MealPlanDraft)
    if status_filter is not None:
        stmt = stmt.where(models.MealPlanDraft.status == status_filter)
    return db.execute(stmt.order_by(models.MealPlanDraft.updated_at.desc())).scalars().all()


@router.get("/drafts/{draft_id}", response_model=schemas.MealPlanDraftDetail)
def get_plan_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_plan_or_404(draft_id, db)


@router.post("/drafts/{draft_id}/approve", response_model=list[schemas.MealPlanEntryRead])
def approve_plan_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Turn a proposed week into real entries. This is the gate.

    References are resolved again here rather than trusted from when the draft
    was made: a recipe can be deleted between proposing and approving, and
    planning a week around a recipe that no longer exists is worse than saying
    so. Nothing is written if any of them fail -- a half-approved week is the
    worst of the available outcomes.
    """
    draft = _get_plan_or_404(draft_id, db)
    if draft.status in _SETTLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This plan is {draft.status.value} and can no longer be approved.",
        )
    if not draft.meals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This plan has no meals in it."
        )

    wanted = {uuid.UUID(meal["recipe_id"]) for meal in draft.meals}
    found = set(db.execute(select(models.Recipe.id).where(models.Recipe.id.in_(wanted))).scalars())
    if missing := wanted - found:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Some recipes in this plan no longer exist: "
                f"{', '.join(sorted(str(m) for m in missing))}. Edit the plan or discard it."
            ),
        )

    entries = [
        models.MealPlanEntry(
            date=date.fromisoformat(meal["date"]),
            recipe_id=uuid.UUID(meal["recipe_id"]),
            # The only place this is ever set. It records that the week was
            # proposed rather than chosen meal by meal.
            mode=models.MealPlanMode.auto,
            meal_type=meal.get("meal_type"),
            servings=meal.get("servings"),
        )
        for meal in draft.meals
    ]
    db.add_all(entries)

    draft.status = models.DraftStatus.promoted
    draft.approved_at = datetime.now(timezone.utc)
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return entries


@router.post("/drafts/{draft_id}/discard", response_model=schemas.MealPlanDraftDetail)
def discard_plan_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Say no, and keep the record of having said no."""
    draft = _get_plan_or_404(draft_id, db)
    if draft.status in _SETTLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This plan is already {draft.status.value}.",
        )
    draft.status = models.DraftStatus.discarded
    db.commit()
    db.refresh(draft)
    return draft


@router.patch("/drafts/{draft_id}", response_model=schemas.MealPlanDraftDetail)
def update_plan_draft(
    draft_id: uuid.UUID, payload: schemas.MealPlanDraftUpdate, db: Session = Depends(get_db)
):
    """Edit a proposed week before approving it.

    Swapping Thursday's meal is the normal case -- a plan that can only be
    taken whole or rejected whole is one that gets rejected.
    """
    draft = _get_plan_or_404(draft_id, db)
    if draft.status in _SETTLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This plan is {draft.status.value} and can no longer be changed.",
        )
    data = payload.model_dump(exclude_unset=True, mode="json")
    if "title" in data:
        draft.title = data["title"]
    if "note" in data:
        draft.note = data["note"]
    if data.get("meals") is not None:
        draft.meals = data["meals"]
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/drafts/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Hard delete, for a plan created by mistake.

    Unlike a promoted recipe draft there is nothing to strip: the entries an
    approved plan created stand on their own and are not deleted with it.
    """
    db.delete(_get_plan_or_404(draft_id, db))
    db.commit()


# --------------------------------------------------------------------------
# individual entries
# --------------------------------------------------------------------------


@router.patch("/{entry_id}", response_model=schemas.MealPlanEntryRead)
def update_entry(
    entry_id: uuid.UUID, payload: schemas.MealPlanEntryUpdate, db: Session = Depends(get_db)
):
    """Move an entry, or change the servings or meal slot planned for it."""
    entry = db.get(models.MealPlanEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)):
    entry = db.get(models.MealPlanEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    db.delete(entry)
    db.commit()
