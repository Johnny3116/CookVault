"""Editing the aisle mapping, and asking it what it thinks.

The rules are data, so this is ordinary CRUD. The one endpoint worth its keep
beyond that is `/aisles/resolve`, which answers "why is this in that aisle" by
naming the rule that won -- a mapping you cannot interrogate is one you end up
fighting.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.services.aisles import Rule, match_rule

router = APIRouter(prefix="/aisles", tags=["aisles"], dependencies=[Depends(require_auth)])


def load_rules(db: Session) -> list[Rule]:
    rows = db.execute(select(models.AisleRule)).scalars().all()
    return [Rule(term=row.term, aisle=row.aisle) for row in rows]


def _get_rule_or_404(rule_id: uuid.UUID, db: Session) -> models.AisleRule:
    rule = db.get(models.AisleRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aisle rule not found")
    return rule


@router.get("", response_model=list[str])
def list_aisles():
    """The aisles themselves, in the order a shop is walked."""
    from app.services.aisles import AISLE_ORDER

    return [aisle.value for aisle in AISLE_ORDER]


@router.get("/rules", response_model=list[schemas.AisleRuleRead])
def list_rules(aisle: models.ShoppingAisle | None = None, db: Session = Depends(get_db)):
    stmt = select(models.AisleRule)
    if aisle is not None:
        stmt = stmt.where(models.AisleRule.aisle == aisle)
    return db.execute(stmt.order_by(models.AisleRule.term)).scalars().all()


@router.post("/rules", response_model=schemas.AisleRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(payload: schemas.AisleRuleCreate, db: Session = Depends(get_db)):
    term = payload.term.strip()
    if not term:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A rule needs a term.")

    rule = models.AisleRule(term=term, aisle=payload.aisle)
    db.add(rule)
    try:
        db.commit()
    except IntegrityError:
        # The term is unique: two rules for one word would make the winner
        # depend on row order, which is not a reason.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"There is already a rule for {term!r}.",
        ) from None
    db.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}", response_model=schemas.AisleRuleRead)
def update_rule(
    rule_id: uuid.UUID, payload: schemas.AisleRuleUpdate, db: Session = Depends(get_db)
):
    rule = _get_rule_or_404(rule_id, db)
    data = payload.model_dump(exclude_unset=True)
    if "term" in data:
        term = (data["term"] or "").strip()
        if not term:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="A rule needs a term."
            )
        rule.term = term
    if "aisle" in data:
        rule.aisle = data["aisle"]
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="There is already a rule for that term."
        ) from None
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(_get_rule_or_404(rule_id, db))
    db.commit()


@router.get("/resolve", response_model=schemas.AisleResolution)
def resolve(name: str, db: Session = Depends(get_db)):
    """Where would this land, and which rule decided?"""
    rule = match_rule(name, load_rules(db))
    return schemas.AisleResolution(
        name=name,
        aisle=rule.aisle if rule else models.ShoppingAisle.other,
        matched_term=rule.term if rule else None,
    )
