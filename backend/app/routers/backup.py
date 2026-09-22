"""Backup and restore.

`POST /backup/restore` replaces the entire library, so it asks for the word
`replace` in the body rather than trusting that whoever called it meant to.
An accidental restore is not recoverable from inside the app -- the thing it
would undo is the very thing you would need.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.services.backup import RestoreError, export_library, restore_library

router = APIRouter(prefix="/backup", tags=["backup"], dependencies=[Depends(require_auth)])


class RestoreRequest(BaseModel):
    """A backup file, plus an explicit confirmation."""

    # The word "replace", typed out. This wipes everything currently stored.
    confirm: str
    data: dict


@router.get("/export")
def export_everything(db: Session = Depends(get_db)):
    """The whole library as JSON: recipes and their children, drafts,
    provenance, the plan, the shopping list, history, pantry and aisle rules.

    Ids are preserved on purpose, so a restore can be checked by comparing it
    against the export it came from."""
    return export_library(db)


@router.post("/restore")
def restore_everything(payload: RestoreRequest, db: Session = Depends(get_db)):
    """Replace everything with the contents of a backup."""
    if payload.confirm != "replace":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restoring replaces the entire library. Send confirm=\"replace\" to proceed.",
        )
    try:
        counts = restore_library(db, payload.data)
    except RestoreError as exc:
        # Nothing has been changed -- the whole restore is one transaction.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"restored": counts}
