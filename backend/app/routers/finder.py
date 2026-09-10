from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db

router = APIRouter(prefix="/finder", tags=["finder"], dependencies=[Depends(require_auth)])


class FinderQuery(BaseModel):
    query: str


class FinderResults(BaseModel):
    from_collection: list[schemas.RecipeSummary]
    new_finds: list[schemas.RecipeSummary]
    new_finds_note: str


@router.post("/search", response_model=FinderResults)
def search(payload: FinderQuery, db: Session = Depends(get_db)):
    # Phase 1: naive keyword match against saved recipes only.
    # Phase 2: parse payload.query into structured criteria via
    # app.agent_zero_client.parse_finder_query and also search the web.
    term = payload.query.strip()
    stmt = select(models.Recipe).where(
        models.Recipe.title.ilike(f"%{term}%") | models.Recipe.tags.contains([term])
    )
    matches = db.execute(stmt).scalars().all()
    return FinderResults(
        from_collection=matches,
        new_finds=[],
        new_finds_note="Web search for new recipes isn't implemented yet (Phase 2).",
    )
