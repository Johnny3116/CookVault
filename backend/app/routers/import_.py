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

- **video**: a cooking video's description and spoken transcript, via yt-dlp.
  Both are kept, because the spec's first listed pitfall is that captions alone
  miss a third to a half of a recipe. Only the description is *structured*: see
  `services/video_import.py` for why running a line parser over speech is worse
  than returning an honest blank.

Model-assisted structuring is the one still missing, and it is what would make
the transcript half worth more than a reference. It needs a verified Agent Zero
contract -- see `app/agent_zero_client.py`. When it arrives it produces the
same payload and creates a draft through the same function here;
`import_method` on the provenance row is what tells them apart afterwards.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import require_auth
from app.db import get_db
from app.routers.drafts import build_draft
from app.services.recipe_text import parse_recipe_text
from app.services import video_import
from app.services.web_import import SourceFetchError, fetch_page, payload_from_page

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(require_auth)])


def _store(
    db: Session,
    payload: dict,
    provenance: schemas.ProvenanceCreate,
    note: str | None = None,
) -> models.RecipeDraft:
    # The payload is the editable proposal; extracted_payload is a frozen copy
    # of what the importer produced. They start identical and diverge the
    # moment anyone edits the draft, which is what makes "what did I change?"
    # answerable later.
    provenance.extracted_payload = payload
    draft = build_draft(payload.get("title") or None, payload, provenance, note)
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


@router.post("/video", response_model=schemas.RecipeDraftDetail, status_code=status.HTTP_201_CREATED)
def import_from_video(payload: schemas.ImportVideoRequest, db: Session = Depends(get_db)):
    """Read a cooking video into a draft: description, transcript, and both.

    The description is what gets structured. The transcript is kept beside it
    because the spec's first listed pitfall is that captions alone miss a third
    to a half of a recipe -- so when the description says "season to taste" and
    the video says "a teaspoon of salt", the second one is there to be found.

    What could not be worked out is said out loud in the draft's note rather
    than guessed at. A draft that admits it is empty is more useful than one
    full of sentences parsed into ingredients.
    """
    try:
        source = video_import.fetch_video(str(payload.url))
    except SourceFetchError as exc:
        # An unsupported host, a private video, a dead link: the caller's
        # problem to fix, so 400 rather than a 500 that reads like CookVault
        # broke.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = video_import.payload_from_video(source)
    if payload.title:
        result.payload["title"] = payload.title

    return _store(
        db,
        result.payload,
        schemas.ProvenanceCreate(
            source_type=source.source_type,
            source_url=source.url,
            # The channel, when there is one: "who made this" is most of what
            # you want to know about a recipe from a video.
            source_title=source.uploader or source.title,
            import_method=models.ImportMethod.video_fetch,
            original_text=video_import.original_text(source),
        ),
        note=" ".join([result.note, *result.warnings]),
    )
