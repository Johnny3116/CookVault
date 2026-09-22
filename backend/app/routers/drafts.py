"""The staging area: create, edit, validate, promote.

Every state change a draft can undergo is an explicit endpoint here, and
promotion is the only route from a draft into `recipes`. That matters more
than it looks: when an agent is eventually allowed to propose recipes, it gets
POST /drafts and nothing else, and the rest of this file is the review it has
to pass through. The door is the same one the "new draft" button uses.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.routers.recipes import _apply_children
from app.services.drafts import DraftIssue, has_errors, validate_payload

router = APIRouter(prefix="/drafts", tags=["drafts"], dependencies=[Depends(require_auth)])

# A promoted draft is history: it records what was approved and what came of
# it. A discarded one is a decision already made. Neither is an editing
# surface, so edits and further transitions are refused rather than silently
# reopening them.
_SETTLED = (models.DraftStatus.promoted, models.DraftStatus.discarded)


def _get_draft_or_404(draft_id: uuid.UUID, db: Session) -> models.RecipeDraft:
    draft = db.get(models.RecipeDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


def _reject_if_settled(draft: models.RecipeDraft) -> None:
    if draft.status in _SETTLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This draft is {draft.status.value} and can no longer be changed.",
        )


def _as_validation(issues: list[DraftIssue]) -> schemas.DraftValidation:
    return schemas.DraftValidation(
        ok=not has_errors(issues),
        issues=[
            schemas.DraftIssueRead(severity=i.severity, field=i.field, message=i.message) for i in issues
        ],
    )


@router.get("", response_model=list[schemas.RecipeDraftSummary])
def list_drafts(status_filter: models.DraftStatus | None = None, db: Session = Depends(get_db)):
    """Drafts, newest activity first -- the list is a work queue."""
    stmt = select(models.RecipeDraft)
    if status_filter is not None:
        stmt = stmt.where(models.RecipeDraft.status == status_filter)
    stmt = stmt.order_by(models.RecipeDraft.updated_at.desc())
    return db.execute(stmt).scalars().all()


@router.post("", response_model=schemas.RecipeDraftDetail, status_code=status.HTTP_201_CREATED)
def create_draft(payload: schemas.RecipeDraftCreate, db: Session = Depends(get_db)):
    draft = models.RecipeDraft(title=payload.title, payload=payload.payload)
    if payload.provenance is not None:
        draft.provenance = models.RecipeProvenance(**payload.provenance.model_dump())
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.get("/{draft_id}", response_model=schemas.RecipeDraftDetail)
def get_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_draft_or_404(draft_id, db)


@router.patch("/{draft_id}", response_model=schemas.RecipeDraftDetail)
def update_draft(
    draft_id: uuid.UUID, payload: schemas.RecipeDraftUpdate, db: Session = Depends(get_db)
):
    """Edit a draft. Any change to the payload un-readies it.

    `ready` means "CookVault validated *this* payload". Letting an edit keep
    that flag would make it a claim about a payload nobody checked, which is
    the one thing the status exists to prevent.
    """
    draft = _get_draft_or_404(draft_id, db)
    _reject_if_settled(draft)

    data = payload.model_dump(exclude_unset=True)
    if "title" in data:
        draft.title = data["title"]
    if "payload" in data and data["payload"] is not None:
        draft.payload = data["payload"]
        if draft.status == models.DraftStatus.ready:
            draft.status = models.DraftStatus.draft
    db.commit()
    db.refresh(draft)
    return draft


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Hard delete, provenance and all -- for drafts created by mistake.

    To reject a real proposal and keep the record of having rejected it, use
    /discard instead.
    """
    draft = _get_draft_or_404(draft_id, db)
    if draft.status == models.DraftStatus.promoted:
        # Its provenance row is the promoted recipe's provenance row. Deleting
        # the draft would cascade it away and quietly strip the cookbook entry
        # of the record of where it came from.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This draft was promoted; deleting it would erase the recipe's provenance.",
        )
    db.delete(draft)
    db.commit()


@router.post("/{draft_id}/validate", response_model=schemas.DraftValidation)
def validate_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Check a draft and record the verdict as its status.

    Read-only as far as the payload is concerned: validation reports, it never
    repairs. Silently fixing a proposal would hide exactly what the reviewer
    is here to see.
    """
    draft = _get_draft_or_404(draft_id, db)
    _reject_if_settled(draft)

    issues = validate_payload(draft.payload)
    result = _as_validation(issues)
    draft.status = models.DraftStatus.ready if result.ok else models.DraftStatus.draft
    db.commit()
    return result


@router.post("/{draft_id}/discard", response_model=schemas.RecipeDraftDetail)
def discard_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    draft = _get_draft_or_404(draft_id, db)
    _reject_if_settled(draft)
    draft.status = models.DraftStatus.discarded
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/{draft_id}/promote", response_model=schemas.RecipeDetail, status_code=status.HTTP_201_CREATED)
def promote_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)):
    """Turn an approved draft into a real recipe.

    Validation runs again here rather than trusting the stored `ready` flag.
    The flag is a convenience for the UI; this is the gate, and a gate that
    trusts a cached answer is not a gate.

    The draft's provenance moves onto the recipe -- the same row, now pointing
    at both -- so the cookbook entry keeps the record of where it came from
    without a copy that can drift.
    """
    draft = _get_draft_or_404(draft_id, db)
    _reject_if_settled(draft)

    issues = validate_payload(draft.payload)
    if has_errors(issues):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_as_validation(issues).model_dump(),
        )

    parsed = schemas.RecipeCreate.model_validate(draft.payload)
    recipe = models.Recipe(**parsed.model_dump(exclude={"ingredients", "steps", "alternates"}))
    _apply_children(recipe, parsed)
    db.add(recipe)
    db.flush()  # need the recipe's id before pointing provenance at it

    if draft.provenance is not None:
        draft.provenance.recipe_id = recipe.id

    draft.status = models.DraftStatus.promoted
    draft.promoted_recipe_id = recipe.id
    draft.promoted_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(recipe)
    return recipe
