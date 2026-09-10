from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import require_auth

router = APIRouter(prefix="/import", tags=["import"], dependencies=[Depends(require_auth)])


class ImportRequest(BaseModel):
    url: str


@router.post("", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def import_from_url(payload: ImportRequest):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Video/web import isn't implemented yet. Phase 2 needs yt-dlp transcript "
            "extraction, web scraping, and the Agent Zero integration to structure the "
            "result -- see app/agent_zero_client.py."
        ),
    )
