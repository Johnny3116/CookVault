"""Import a recipe from somewhere else -- into a draft, never into the cookbook.

That distinction is the entire design. An importer is a thing that reads text
written by a stranger and produces structure it is sometimes wrong about, so
its output belongs in the review queue by construction rather than by
convention. There is no flag here to skip that.

Two sources work today, both deterministic:

- **paste**: text goes through the line heuristic in `services/recipe_text.py`.
- **url**: the page's `schema.org/Recipe` JSON-LD is read if present (the
  amounts the publisher actually typed), and the text heuristic is the
  fallback if not.

Video transcripts and model-assisted structuring are the missing third source.
They need yt-dlp and a verified Agent Zero contract -- see
`app/agent_zero_client.py`. When they arrive they produce the same payload and
create a draft through the same function; `import_method="agent"` on the
provenance row is what will tell the two apart afterwards.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.routers.drafts import build_draft
from app.services.recipe_text import parse_recipe_text
from app.services.web_import import SourceFetchError, fetch_page, payload_from_page

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(require_auth)])


def _store(
    db: Session,
    payload: dict,
    provenance: schemas.ProvenanceCreate,
) -> models.RecipeDraft:
    # The payload is the editable proposal; extracted_payload is a frozen copy
    # of what the importer produced. They start identical and diverge the
    # moment anyone edits the draft, which is what makes "what did I change?"
    # answerable later.
    provenance.extracted_payload = payload
    draft = build_draft(payload.get("title") or None, payload, provenance)
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.post("", response_model=schemas.RecipeDraftDetail, status_code=status.HTTP_201_CREATED)
def import_from_url(payload: schemas.ImportUrlRequest, db: Session = Depends(get_db)):
    """Fetch a recipe page and stage what it says as a draft."""
    try:
        page_html = fetch_page(str(payload.url))
    except SourceFetchError as exc:
        # The URL was bad, private, or unreachable -- the caller's problem to
        # fix, so 400 rather than a 500 that reads like CookVault broke.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    parsed, source_text, from_jsonld = payload_from_page(page_html)

    return _store(
        db,
        parsed,
        schemas.ProvenanceCreate(
            source_type=payload.source_type,
            source_url=str(payload.url),
            source_title=payload.source_title or parsed.get("title") or None,
            import_method=models.ImportMethod.url_fetch,
            # For a JSON-LD page this is the publisher's own structured data,
            # not the rendered article: it is the closest thing to "what the
            # source actually said", and far more readable than the HTML.
            original_text=source_text,
        ),
    )


@router.post("/paste", response_model=schemas.RecipeDraftDetail, status_code=status.HTTP_201_CREATED)
def import_from_paste(payload: schemas.ImportPasteRequest, db: Session = Depends(get_db)):
    """Stage pasted recipe text as a draft.

    No network, no fetching, no parsing anybody else's markup -- which makes
    this the path that always works, including for a photographed card typed
    out by hand or a recipe dictated over the phone.
    """
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="There's no text to import."
        )

    parsed = parse_recipe_text(payload.text)
    if payload.title:
        parsed["title"] = payload.title

    return _store(
        db,
        parsed,
        schemas.ProvenanceCreate(
            source_type=payload.source_type,
            source_url=payload.source_url,
            source_title=payload.source_title,
            import_method=models.ImportMethod.paste,
            original_text=payload.text,
        ),
    )
